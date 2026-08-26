from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.privacy.models import BackgroundJob


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    dedup_key: str,
    payload: dict,
    now: datetime,
    max_attempts: int = 8,
) -> UUID | None:
    job_id = uuid4()
    stmt = (
        insert(BackgroundJob)
        .values(
            job_id=job_id,
            job_type=job_type,
            dedup_key=dedup_key,
            payload=payload,
            status="queued",
            attempts=0,
            max_attempts=max_attempts,
            run_after=now,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(BackgroundJob.job_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return row[0]
