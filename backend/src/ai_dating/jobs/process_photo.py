from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.models import AiOperation
from ai_dating.config import Settings
from ai_dating.jobs.claim import ClaimedJob
from ai_dating.media.constants import JOB_TYPE_PROCESS_PHOTO
from ai_dating.media.images import decode_image, render_derivative
from ai_dating.media.models import ProfilePhoto
from ai_dating.media.storage import open_store
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.activation import maybe_activate
from ai_dating.profiles.models import Profile
from ai_dating.profiles.service import bump_profile

log = structlog.get_logger("ai_dating.jobs")


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
    commit: bool = True,
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
    if commit:
        db.commit()


def process_photo_job(db: Session, settings: Settings, job: ClaimedJob) -> None:
    payload = job.payload
    try:
        photo_id = UUID(str(payload["photo_id"]))
        photo_version = int(payload["photo_version"])
    except (KeyError, ValueError, TypeError):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    if job.job_type != JOB_TYPE_PROCESS_PHOTO:
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    photo = db.get(ProfilePhoto, photo_id)
    if photo is None or photo.deleted_at is not None or photo.version != photo_version:
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    store = open_store(settings)
    stored = store.get(photo.object_key)
    if not stored.exists or stored.body is None:
        retry = job.attempts < job.max_attempts
        _mark(
            db,
            job.job_id,
            status="queued" if retry else "failed",
            error_code="missing_object",
            run_after=_now() + _backoff(job.attempts) if retry else None,
        )
        return
    try:
        image = decode_image(stored.body)
        derived, width, height = render_derivative(image, settings.photo_max_edge)
    except ValueError:
        photo.moderation_state = "rejected"
        photo.moderated_at = _now()
        db.add(
            AiOperation(
                ai_operation_id=uuid4(),
                job_id=job.job_id,
                operation_type="moderation",
                prompt_version="photo-derivative-v1",
                model_version="local-decode",
                source_entity_type="profile_photo",
                source_entity_id=photo.photo_id,
                source_version=photo.version,
                latency_ms=None,
                token_input=None,
                token_output=None,
                result_status="safety_rejected",
                safety_result="rejected",
                created_at=_now(),
            )
        )
        _mark(db, job.job_id, status="succeeded", error_code="invalid_image")
        return
    derived_key = f"{photo.object_key}-derived.jpg"
    store.put(derived_key, derived, "image/jpeg")
    now = _now()
    photo.derived_object_key = derived_key
    photo.width = width
    photo.height = height
    if settings.media_auto_approve:
        photo.moderation_state = "approved"
        photo.moderated_at = now
        result_status = "succeeded"
        safety = "passed"
    else:
        result_status = "succeeded"
        safety = "skipped"
    db.add(
        AiOperation(
            ai_operation_id=uuid4(),
            job_id=job.job_id,
            operation_type="moderation",
            prompt_version="photo-derivative-v1",
            model_version="local-decode",
            source_entity_type="profile_photo",
            source_entity_id=photo.photo_id,
            source_version=photo.version,
            latency_ms=None,
            token_input=None,
            token_output=None,
            result_status=result_status,
            safety_result=safety,
            created_at=now,
        )
    )
    profile = db.get(Profile, photo.profile_id)
    if profile is not None:
        bump_profile(profile, now)
        account = db.get(Account, profile.account_id)
        if account is not None:
            maybe_activate(db, settings, account, profile, now, producer="worker")
    _mark(db, job.job_id, status="succeeded", commit=False)
    db.commit()
    log.info(
        "photo_process_ok",
        job_id=str(job.job_id),
        moderation_state=photo.moderation_state,
    )


def cleanup_media_job(db: Session, settings: Settings, job: ClaimedJob) -> None:
    payload = job.payload
    keys = [
        str(payload.get("object_key") or ""),
        str(payload.get("derived_object_key") or ""),
    ]
    store = open_store(settings)
    for key in keys:
        if key:
            store.delete(key)
    _mark(db, job.job_id, status="succeeded")
    log.info("media_cleanup_ok", job_id=str(job.job_id))
