from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from ai_dating.config import Settings
from ai_dating.jobs.claim import ClaimedJob
from ai_dating.messaging.constants import JOB_TYPE_MODERATE_MESSAGE
from ai_dating.messaging.models import Message
from ai_dating.messaging.service import apply_message_moderation
from ai_dating.privacy.models import BackgroundJob

log = structlog.get_logger("ai_dating.jobs")


def _now() -> datetime:
    return datetime.now(UTC)


def _mark(
    db: Session,
    job_id: UUID,
    *,
    status: str,
    error_code: str | None = None,
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
    if commit:
        db.commit()


def process_moderate_message_job(
    db: Session, settings: Settings, job: ClaimedJob
) -> None:
    payload = job.payload
    try:
        message_id = UUID(str(payload["message_id"]))
    except (KeyError, ValueError, TypeError):
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    if job.job_type != JOB_TYPE_MODERATE_MESSAGE:
        _mark(db, job.job_id, status="failed", error_code="schema_invalid")
        return
    message = db.get(Message, message_id)
    if message is None or message.deleted_at is not None:
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    if message.moderation_state != "held":
        _mark(db, job.job_id, status="succeeded", error_code="stale")
        return
    if settings.message_auto_approve:
        apply_message_moderation(db, message, "allowed", job_id=job.job_id)
    _mark(db, job.job_id, status="succeeded", commit=False)
    db.commit()
    log.info(
        "message_moderate_ok",
        job_id=str(job.job_id),
        moderation_state=message.moderation_state,
    )
