from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.ai.extract import ProviderError, run_extraction
from ai_dating.ai.models import AiOperation
from ai_dating.ai.schema import (
    EXTRACTION_MODEL_VERSION,
    EXTRACTION_PROMPT_VERSION,
    FACT_CODES,
    JOB_TYPE_EXTRACT,
    PREFERENCE_STRENGTHS,
    ExtractionRejected,
    normalize_excerpt,
)
from ai_dating.config import Settings
from ai_dating.jobs.claim import ClaimedJob
from ai_dating.onboarding.steps import record_step
from ai_dating.onboarding.vocab import prompt_side
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.models import Profile, ProfileAnswer, ProfileFact

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
    safety_result: str,
    latency_ms: int | None,
    token_input: int | None,
    token_output: int | None,
    source_id: UUID,
    source_version: int,
    prompt_version: str,
    model_version: str,
) -> None:
    db.add(
        AiOperation(
            ai_operation_id=uuid4(),
            job_id=job.job_id,
            operation_type="extraction",
            prompt_version=prompt_version,
            model_version=model_version,
            source_entity_type="profile_answer",
            source_entity_id=source_id,
            source_version=source_version,
            latency_ms=latency_ms,
            token_input=token_input,
            token_output=token_output,
            result_status=result_status,
            safety_result=safety_result,
            created_at=_now(),
        )
    )


def _active_fact(
    db: Session, profile_id: UUID, side: str, fact_code: str, value: str
) -> ProfileFact | None:
    return db.scalar(
        select(ProfileFact).where(
            ProfileFact.profile_id == profile_id,
            ProfileFact.profile_side == side,
            ProfileFact.fact_code == fact_code,
            ProfileFact.value == value,
            ProfileFact.superseded_at.is_(None),
            ProfileFact.review_state != "rejected",
        )
    )


def _supersede_pending_source(
    db: Session, answer: ProfileAnswer, now: datetime
) -> None:
    rows = list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.source_id == answer.answer_id,
                ProfileFact.superseded_at.is_(None),
                ProfileFact.review_state == "pending",
            )
        )
    )
    for row in rows:
        row.superseded_at = now
    if rows:
        db.flush()


def _write_pending(
    db: Session,
    answer: ProfileAnswer,
    facts: list[dict],
    prompt_version: str,
    model_version: str,
) -> None:
    now = _now()
    side = prompt_side(answer.prompt_code)
    excerpt_fallback = normalize_excerpt(answer.answer_text)
    _supersede_pending_source(db, answer, now)
    for item in facts:
        current = _active_fact(
            db, answer.profile_id, side, item["fact_code"], item["value"]
        )
        if current is not None and current.review_state == "confirmed":
            continue
        spec = FACT_CODES[item["fact_code"]]
        if spec["kind"] == "ordinal":
            others = list(
                db.scalars(
                    select(ProfileFact).where(
                        ProfileFact.profile_id == answer.profile_id,
                        ProfileFact.profile_side == side,
                        ProfileFact.fact_code == item["fact_code"],
                        ProfileFact.superseded_at.is_(None),
                        ProfileFact.review_state == "pending",
                    )
                )
            )
            for old in others:
                if current is None or old.fact_id != current.fact_id:
                    old.superseded_at = now
            db.flush()
        if current is not None:
            current.superseded_at = now
            db.flush()
        strength = None
        if side == "desired_partner":
            raw_strength = item.get("preference_strength")
            strength = (
                raw_strength if raw_strength in PREFERENCE_STRENGTHS else "prefer"
            )
        db.add(
            ProfileFact(
                fact_id=uuid4(),
                profile_id=answer.profile_id,
                profile_side=side,
                fact_code=item["fact_code"],
                value=item["value"],
                preference_strength=strength,
                source_type="free_text",
                source_id=answer.answer_id,
                source_version=answer.version,
                provenance_excerpt=item["excerpt"] or excerpt_fallback,
                confidence=Decimal(str(item["confidence"])),
                review_state="pending",
                visibility="private",
                valid_from=now,
                extractor_version=prompt_version,
                prompt_version=prompt_version,
                model_version=model_version,
            )
        )


def _maybe_facts_step(db: Session, answer: ProfileAnswer) -> None:
    pending = db.scalar(
        select(ProfileFact.fact_id).where(
            ProfileFact.profile_id == answer.profile_id,
            ProfileFact.superseded_at.is_(None),
            ProfileFact.review_state == "pending",
        )
    )
    if pending is not None:
        return
    profile = db.get(Profile, answer.profile_id)
    if profile is None:
        return
    from ai_dating.accounts.models import Account
    from ai_dating.onboarding.steps import load_preferences

    account = db.get(Account, profile.account_id)
    if account is None:
        return
    record_step(
        db,
        account,
        "facts_review",
        profile=profile,
        prefs=load_preferences(db, account.account_id),
    )


def process_extract_job(db: Session, settings: Settings, job: ClaimedJob) -> None:
    payload = job.payload
    try:
        answer_id = UUID(str(payload["answer_id"]))
        answer_version = int(payload["answer_version"])
        prompt_version = str(payload.get("prompt_version") or EXTRACTION_PROMPT_VERSION)
        model_version = str(payload.get("model_version") or EXTRACTION_MODEL_VERSION)
    except (KeyError, ValueError, TypeError):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    answer = db.get(ProfileAnswer, answer_id)
    if (
        answer is None
        or answer.deleted_at is not None
        or answer.version != answer_version
    ):
        _observe(
            db,
            job,
            result_status="stale",
            safety_result="skipped",
            latency_ms=None,
            token_input=None,
            token_output=None,
            source_id=answer_id,
            source_version=answer_version,
            prompt_version=prompt_version,
            model_version=model_version,
        )
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    try:
        facts, result = run_extraction(settings, answer.prompt_code, answer.answer_text)
    except ExtractionRejected as exc:
        _observe(
            db,
            job,
            result_status=exc.code,
            safety_result="rejected" if exc.code == "safety_rejected" else "skipped",
            latency_ms=None,
            token_input=None,
            token_output=None,
            source_id=answer.answer_id,
            source_version=answer.version,
            prompt_version=prompt_version,
            model_version=model_version,
        )
        _maybe_facts_step(db, answer)
        _mark(db, job.job_id, status="failed", error_code=exc.code)
        log.info("extraction_rejected", error_code=exc.code, job_id=str(job.job_id))
        return
    except ProviderError as exc:
        code = (
            str(exc)
            if str(exc) in _RETRYABLE or str(exc) == "schema_invalid"
            else "provider_error"
        )
        retry = code in _RETRYABLE and job.attempts < job.max_attempts
        _observe(
            db,
            job,
            result_status=(
                "provider_error" if code != "schema_invalid" else "schema_invalid"
            ),
            safety_result="skipped",
            latency_ms=None,
            token_input=None,
            token_output=None,
            source_id=answer.answer_id,
            source_version=answer.version,
            prompt_version=prompt_version,
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
        _maybe_facts_step(db, answer)
        _mark(db, job.job_id, status="failed", error_code=code)
        return
    _write_pending(db, answer, facts, prompt_version, model_version)
    _observe(
        db,
        job,
        result_status="succeeded",
        safety_result="passed",
        latency_ms=result.latency_ms,
        token_input=result.token_input,
        token_output=result.token_output,
        source_id=answer.answer_id,
        source_version=answer.version,
        prompt_version=prompt_version,
        model_version=model_version,
    )
    _maybe_facts_step(db, answer)
    _mark(db, job.job_id, status="succeeded")
    log.info("extraction_ok", job_id=str(job.job_id), fact_count=len(facts))


def run_once(db: Session, settings: Settings, jobs: list[ClaimedJob]) -> None:
    for job in jobs:
        if job.job_type != JOB_TYPE_EXTRACT:
            continue
        process_extract_job(db, settings, job)
