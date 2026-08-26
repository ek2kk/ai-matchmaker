from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_dating.ai.schema import JOB_TYPE_EMBED, JOB_TYPE_EXTRACT
from ai_dating.media.constants import JOB_TYPE_CLEANUP_MEDIA, JOB_TYPE_PROCESS_PHOTO
from ai_dating.messaging.constants import JOB_TYPE_MODERATE_MESSAGE
from ai_dating.privacy.models import BackgroundJob
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    job_type: str
    payload: dict
    attempts: int
    max_attempts: int


def _now() -> datetime:
    return datetime.now(UTC)


def claim_jobs(
    db: Session,
    *,
    limit: int,
    lease_seconds: int,
    job_types: tuple[str, ...] = (
        JOB_TYPE_EXTRACT,
        JOB_TYPE_EMBED,
        JOB_TYPE_GENERATE,
        JOB_TYPE_PROCESS_PHOTO,
        JOB_TYPE_CLEANUP_MEDIA,
        JOB_TYPE_MODERATE_MESSAGE,
    ),
) -> list[ClaimedJob]:
    now = _now()
    rows = (
        db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.job_type.in_(job_types),
                BackgroundJob.run_after <= now,
                or_(
                    BackgroundJob.status == "queued",
                    BackgroundJob.lease_until < now,
                ),
            )
            .order_by(BackgroundJob.run_after)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    until = now + timedelta(seconds=lease_seconds)
    claimed: list[ClaimedJob] = []
    for row in rows:
        row.status = "running"
        row.lease_until = until
        row.attempts += 1
        row.updated_at = now
        claimed.append(
            ClaimedJob(
                job_id=row.job_id,
                job_type=row.job_type,
                payload=dict(row.payload),
                attempts=row.attempts,
                max_attempts=row.max_attempts,
            )
        )
    db.commit()
    return claimed
