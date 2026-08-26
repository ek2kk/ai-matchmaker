from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.schema import (
    FACT_CODES,
    JOB_TYPE_EMBED,
    JOB_TYPE_EXTRACT,
    event_source_type,
    fact_category,
    fact_purpose,
    validate_fact_value,
    validate_preference_strength,
    validate_profile_side,
    validate_visibility,
)
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.onboarding.steps import load_preferences, record_step
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.embeddings import embedding_status, enqueue_embeddings
from ai_dating.profiles.models import Profile, ProfileAnswer, ProfileFact
from ai_dating.profiles.service import bump_profile, require_profile
from ai_dating.recommendations.enqueue import enqueue_generation

_FACT_STATES = {
    "pending": ("pending",),
    "confirmed": ("confirmed",),
    "rejected": ("rejected",),
    "current": ("pending", "confirmed"),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _active_clause():
    return ProfileFact.superseded_at.is_(None)


def active_fact(
    db: Session,
    profile_id: UUID,
    profile_side: str,
    fact_code: str,
    value: str,
) -> ProfileFact | None:
    return db.scalar(
        select(ProfileFact).where(
            ProfileFact.profile_id == profile_id,
            ProfileFact.profile_side == profile_side,
            ProfileFact.fact_code == fact_code,
            ProfileFact.value == value,
            _active_clause(),
            ProfileFact.review_state != "rejected",
        )
    )


def active_code_facts(
    db: Session, profile_id: UUID, profile_side: str, fact_code: str
) -> list[ProfileFact]:
    return list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile_id,
                ProfileFact.profile_side == profile_side,
                ProfileFact.fact_code == fact_code,
                _active_clause(),
                ProfileFact.review_state != "rejected",
            )
        )
    )


def matching_facts(db: Session, profile_id: UUID) -> list[ProfileFact]:
    return list(
        db.scalars(
            select(ProfileFact).where(
                ProfileFact.profile_id == profile_id,
                _active_clause(),
                ProfileFact.review_state == "confirmed",
                ProfileFact.visibility.in_(("matching_only", "eligible_only")),
            )
        )
    )


def extraction_status(db: Session, profile: Profile | None) -> dict:
    if profile is None:
        return {"status": "idle", "error_code": None}
    answers = list(
        db.scalars(
            select(ProfileAnswer).where(
                ProfileAnswer.profile_id == profile.profile_id,
                ProfileAnswer.deleted_at.is_(None),
            )
        )
    )
    if not answers:
        return {"status": "idle", "error_code": None}
    current = {(row.answer_id, row.version) for row in answers}
    jobs = list(
        db.scalars(
            select(BackgroundJob).where(BackgroundJob.job_type == JOB_TYPE_EXTRACT)
        )
    )
    relevant = []
    for job in jobs:
        payload = job.payload if isinstance(job.payload, dict) else {}
        try:
            key = (
                UUID(str(payload.get("answer_id"))),
                int(payload.get("answer_version", 0)),
            )
        except (ValueError, TypeError):
            continue
        if key in current:
            relevant.append(job)
    if any(job.status in {"queued", "running"} for job in relevant):
        status = (
            "running" if any(job.status == "running" for job in relevant) else "queued"
        )
        return {"status": status, "error_code": None}
    failed = [job for job in relevant if job.status == "failed"]
    if failed and all(job.status == "failed" for job in relevant):
        return {"status": "failed", "error_code": failed[-1].last_error_code}
    if any(job.status == "succeeded" for job in relevant):
        return {"status": "succeeded", "error_code": None}
    return {"status": "idle", "error_code": None}


def pending_jobs(db: Session, profile: Profile | None) -> list[dict]:
    out: list[dict] = []
    extract = extraction_status(db, profile)
    if extract["status"] in {"queued", "running"}:
        out.append({"job_type": JOB_TYPE_EXTRACT, "status": extract["status"]})
    embed = embedding_status(db, profile)
    if embed["status"] in {"queued", "running"}:
        out.append({"job_type": JOB_TYPE_EMBED, "status": embed["status"]})
    return out


def facts_reviewed(db: Session, profile: Profile | None) -> bool:
    if profile is None:
        return False
    status = extraction_status(db, profile)
    if status["status"] in {"queued", "running"}:
        return False
    pending = db.scalar(
        select(ProfileFact.fact_id).where(
            ProfileFact.profile_id == profile.profile_id,
            _active_clause(),
            ProfileFact.review_state == "pending",
        )
    )
    return pending is None


def fact_view(row: ProfileFact) -> dict:
    return {
        "fact_id": str(row.fact_id),
        "profile_side": row.profile_side,
        "fact_code": row.fact_code,
        "value": row.value,
        "preference_strength": row.preference_strength,
        "review_state": row.review_state,
        "visibility": row.visibility,
        "purpose": fact_purpose(row.fact_code),
        "confidence": None if row.confidence is None else float(row.confidence),
        "provenance_excerpt": row.provenance_excerpt,
        "source_type": row.source_type,
        "source_version": row.source_version,
        "extractor_version": row.extractor_version,
        "valid_from": _iso(row.valid_from),
        "reviewed_at": _iso(row.reviewed_at),
    }


def _cursor_decode(after: str | None) -> UUID | None:
    if not after:
        return None
    try:
        return UUID(after)
    except ValueError:
        raise AppError(422, "validation_error", "Invalid request.") from None


def list_facts(
    db: Session,
    account: Account,
    *,
    state: str = "current",
    limit: int = 20,
    after: str | None = None,
) -> dict:
    profile = require_profile(db, account)
    if state not in _FACT_STATES:
        raise AppError(422, "validation_error", "Invalid request.")
    bound = min(max(limit, 1), 50)
    stmt: Select[tuple[ProfileFact]] = (
        select(ProfileFact)
        .where(
            ProfileFact.profile_id == profile.profile_id,
            ProfileFact.review_state.in_(_FACT_STATES[state]),
        )
        .order_by(ProfileFact.valid_from.desc(), ProfileFact.fact_id.desc())
    )
    if state != "rejected":
        stmt = stmt.where(_active_clause())
    marker_id = _cursor_decode(after)
    if marker_id is not None:
        marker = db.get(ProfileFact, marker_id)
        if marker is None or marker.profile_id != profile.profile_id:
            raise AppError(404, "not_found", "Not found.")
        stmt = stmt.where(
            (ProfileFact.valid_from < marker.valid_from)
            | (
                (ProfileFact.valid_from == marker.valid_from)
                & (ProfileFact.fact_id < marker.fact_id)
            )
        )
    rows = list(db.scalars(stmt.limit(bound + 1)))
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        next_cursor = str(rows[-1].fact_id)
    return {
        "items": [fact_view(row) for row in rows],
        "next_cursor": next_cursor,
        "extraction": extraction_status(db, profile),
    }


def _reviewed_event(account_id: UUID, row: ProfileFact, decision: str) -> dict:
    return {
        "event_name": "fact_reviewed",
        "schema_version": 1,
        "producer": "api",
        "owner": "profiles",
        "actor_account_id": str(account_id),
        "subject_account_id": None,
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": None,
        "conversation_id": None,
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": {
            "fact_id": str(row.fact_id),
            "fact_category": fact_category(row.fact_code),
            "decision": decision,
            "source_type": event_source_type(row.source_type),
            "extractor_version": row.extractor_version,
        },
    }


def _bump_if_public(profile: Profile, row: ProfileFact, now: datetime) -> None:
    if (
        row.visibility in {"matching_only", "eligible_only"}
        and row.review_state == "confirmed"
    ):
        bump_profile(profile, now)


def _finish_review(db: Session, account: Account, profile: Profile) -> None:
    if facts_reviewed(db, profile):
        record_step(
            db,
            account,
            "facts_review",
            profile=profile,
            prefs=load_preferences(db, account.account_id),
        )


def _replace_fact(
    db: Session, current: ProfileFact, replacement: ProfileFact, now: datetime
) -> None:
    current.superseded_at = now
    db.flush()
    db.add(replacement)
    db.flush()
    current.superseded_by_id = replacement.fact_id


def create_manual_fact(db: Session, account: Account, body) -> dict:
    profile = require_profile(db, account)
    value = validate_fact_value(body.fact_code, body.value)
    side = validate_profile_side(body.profile_side)
    strength = validate_preference_strength(body.preference_strength, side=side)
    visibility = validate_visibility(body.visibility or "matching_only")
    now = _now()
    row = ProfileFact(
        fact_id=uuid4(),
        profile_id=profile.profile_id,
        profile_side=side,
        fact_code=body.fact_code,
        value=value,
        preference_strength=strength,
        source_type="form",
        source_id=None,
        source_version=None,
        provenance_excerpt=None,
        confidence=None,
        review_state="confirmed",
        visibility=visibility,
        valid_from=now,
        reviewed_at=now,
        extractor_version=None,
        prompt_version=None,
        model_version=None,
    )
    current = active_fact(db, profile.profile_id, side, body.fact_code, value)
    spec = FACT_CODES[body.fact_code]
    if spec["kind"] == "ordinal":
        for old in active_code_facts(db, profile.profile_id, side, body.fact_code):
            if current is None or old.fact_id != current.fact_id:
                old.superseded_at = now
        db.flush()
    if current is not None:
        _replace_fact(db, current, row, now)
    else:
        db.add(row)
        db.flush()
    _bump_if_public(profile, row, now)
    enqueue_event(db, _reviewed_event(account.account_id, row, "edit"))
    enqueue_embeddings(db, profile, _now())
    prefs = load_preferences(db, account.account_id)
    if prefs is not None:
        enqueue_generation(
            db,
            profile=profile,
            prefs=prefs,
            now=_now(),
            trigger_code="profile_updated",
        )
    _finish_review(db, account, profile)
    return fact_view(row)


def review_fact(
    db: Session,
    account: Account,
    fact_id: UUID,
    body,
) -> dict:
    profile = require_profile(db, account)
    row = db.get(ProfileFact, fact_id)
    if row is None or row.profile_id != profile.profile_id:
        raise AppError(404, "not_found", "Not found.")
    if row.superseded_at is not None:
        raise AppError(409, "version_conflict", "Fact changed; reload and retry.")
    if body.expected_source_version is not None and body.expected_source_version != (
        row.source_version or 0
    ):
        raise AppError(
            409,
            "version_conflict",
            "Fact changed; reload and retry.",
            details={"current_version": row.source_version or 0},
        )
    now = _now()
    decision = body.decision
    if decision == "accept":
        if row.review_state != "pending":
            raise AppError(409, "version_conflict", "Fact changed; reload and retry.")
        row.review_state = "confirmed"
        row.reviewed_at = now
        vis = validate_visibility(body.visibility or "matching_only")
        row.visibility = "matching_only" if vis == "private" else vis
        reviewed = row
    elif decision == "reject":
        if row.review_state not in {"pending", "confirmed"}:
            raise AppError(409, "version_conflict", "Fact changed; reload and retry.")
        if row.review_state == "confirmed":
            bump_profile(profile, now)
        row.review_state = "rejected"
        row.reviewed_at = now
        reviewed = row
    elif decision == "edit":
        if body.value is None:
            raise AppError(422, "validation_error", "Invalid request.")
        value = validate_fact_value(row.fact_code, body.value)
        visibility = validate_visibility(body.visibility or "matching_only")
        if visibility == "private":
            visibility = "matching_only"
        replacement = ProfileFact(
            fact_id=uuid4(),
            profile_id=profile.profile_id,
            profile_side=row.profile_side,
            fact_code=row.fact_code,
            value=value,
            preference_strength=row.preference_strength,
            source_type="user_edit",
            source_id=row.source_id,
            source_version=row.source_version,
            provenance_excerpt=row.provenance_excerpt,
            confidence=None,
            review_state="confirmed",
            visibility=visibility,
            valid_from=now,
            reviewed_at=now,
            extractor_version=None,
            prompt_version=None,
            model_version=None,
        )
        _replace_fact(db, row, replacement, now)
        reviewed = replacement
    else:
        raise AppError(422, "validation_error", "Invalid request.")
    _bump_if_public(profile, reviewed, now)
    enqueue_event(db, _reviewed_event(account.account_id, reviewed, decision))
    enqueue_embeddings(db, profile, now)
    prefs = load_preferences(db, account.account_id)
    if prefs is not None:
        enqueue_generation(
            db,
            profile=profile,
            prefs=prefs,
            now=now,
            trigger_code="profile_updated",
        )
    _finish_review(db, account, profile)
    return fact_view(reviewed)
