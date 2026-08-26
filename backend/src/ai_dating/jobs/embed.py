from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.ai.client import embedding_model_version
from ai_dating.ai.embed import ProviderError, run_embedding
from ai_dating.ai.models import AiOperation
from ai_dating.ai.projection import build_projection
from ai_dating.ai.schema import (
    EMBED_KINDS,
    PROJECTION_SCHEMA_VERSION,
)
from ai_dating.config import Settings
from ai_dating.jobs.claim import ClaimedJob
from ai_dating.onboarding.steps import load_preferences
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.facts import matching_facts
from ai_dating.profiles.models import Profile, ProfileAnswer, ProfileEmbedding

log = structlog.get_logger("ai_dating.jobs")
_RETRYABLE = frozenset({"provider_error"})


def _now() -> datetime:
    return datetime.now(UTC)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(60, 2 ** max(1, attempts)))


def _mark(
    db: Session,
    job_id: UUID,
    *,
    status: str,
    error_code: str | None = None,
    run_after: datetime | None = None,
) -> None:
    row = db.get(BackgroundJob, job_id)
    if row is None:
        return
    now = _now()
    row.status = status
    row.last_error_code = error_code
    row.lease_until = None
    row.updated_at = now
    if run_after is not None:
        row.run_after = run_after
    db.commit()


def _observe(
    db: Session,
    job: ClaimedJob,
    *,
    result_status: str,
    latency_ms: int | None,
    token_input: int | None,
    source_id: UUID,
    source_version: int,
    model_version: str,
) -> None:
    db.add(
        AiOperation(
            ai_operation_id=uuid4(),
            job_id=job.job_id,
            operation_type="embedding",
            prompt_version=PROJECTION_SCHEMA_VERSION,
            model_version=model_version,
            source_entity_type="profile",
            source_entity_id=source_id,
            source_version=source_version,
            latency_ms=latency_ms,
            token_input=token_input,
            token_output=None,
            result_status=result_status,
            safety_result="passed" if result_status == "succeeded" else "skipped",
            created_at=_now(),
        )
    )


def process_embed_job(db: Session, settings: Settings, job: ClaimedJob) -> None:
    payload = job.payload
    try:
        profile_id = UUID(str(payload["profile_id"]))
        kind = str(payload["kind"])
        source_version = int(payload["source_version"])
        model_version = str(
            payload.get("model_version") or embedding_model_version(settings)
        )
        if kind not in EMBED_KINDS:
            raise ValueError("kind")
    except (KeyError, ValueError, TypeError):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    profile = db.get(Profile, profile_id)
    if profile is None or profile.deleted_at is not None:
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    if profile.version != source_version:
        _observe(
            db,
            job,
            result_status="stale",
            latency_ms=None,
            token_input=None,
            source_id=profile.profile_id,
            source_version=source_version,
            model_version=model_version,
        )
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    prefs = load_preferences(db, profile.account_id)
    answers = list(
        db.scalars(
            select(ProfileAnswer).where(
                ProfileAnswer.profile_id == profile.profile_id,
                ProfileAnswer.deleted_at.is_(None),
            )
        )
    )
    facts = matching_facts(db, profile.profile_id)
    projection = build_projection(
        kind, profile=profile, prefs=prefs, answers=answers, facts=facts
    )
    try:
        result = run_embedding(settings, str(projection["text"]))
    except ProviderError as exc:
        code = (
            str(exc)
            if str(exc) in {"provider_error", "schema_invalid"}
            else "provider_error"
        )
        retry = code in _RETRYABLE and job.attempts < job.max_attempts
        _observe(
            db,
            job,
            result_status=code,
            latency_ms=None,
            token_input=None,
            source_id=profile.profile_id,
            source_version=source_version,
            model_version=model_version,
        )
        if retry:
            _mark(
                db,
                job.job_id,
                status="queued",
                error_code=code,
                run_after=_now() + _backoff(job.attempts),
            )
            return
        _mark(db, job.job_id, status="failed", error_code=code)
        return
    vector = result.payload
    if not isinstance(vector, list):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    now = _now()
    stmt = (
        insert(ProfileEmbedding)
        .values(
            embedding_id=uuid4(),
            profile_id=profile.profile_id,
            kind=kind,
            source_version=source_version,
            model_version=model_version,
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
            embedding=vector,
            created_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_profile_embeddings_cache")
    )
    db.execute(stmt)
    _observe(
        db,
        job,
        result_status="succeeded",
        latency_ms=result.latency_ms,
        token_input=result.token_input,
        source_id=profile.profile_id,
        source_version=source_version,
        model_version=model_version,
    )
    _mark(db, job.job_id, status="succeeded")
    log.info("embedding_ok", job_id=str(job.job_id), kind=kind)
