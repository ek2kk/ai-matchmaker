from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.ai.client import embedding_model_version
from ai_dating.ai.schema import EMBED_KINDS, JOB_TYPE_EMBED, PROJECTION_SCHEMA_VERSION
from ai_dating.config import load_settings
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.models import Profile


def enqueue_embeddings(db: Session, profile: Profile, now: datetime) -> None:
    if profile.activated_at is None:
        return
    settings = load_settings()
    model_version = embedding_model_version(settings)
    for kind in EMBED_KINDS:
        enqueue_job(
            db,
            job_type=JOB_TYPE_EMBED,
            dedup_key=(
                f"{JOB_TYPE_EMBED}:{profile.profile_id}:{kind}:"
                f"{profile.version}:{PROJECTION_SCHEMA_VERSION}:{model_version}"
            ),
            payload={
                "profile_id": str(profile.profile_id),
                "kind": kind,
                "source_version": profile.version,
                "projection_schema_version": PROJECTION_SCHEMA_VERSION,
                "model_version": model_version,
            },
            now=now,
            max_attempts=settings.extraction_max_attempts,
        )


def embedding_status(db: Session, profile: Profile | None) -> dict:
    if profile is None:
        return {"status": "idle", "error_code": None}
    jobs = [
        job
        for job in db.scalars(
            select(BackgroundJob).where(BackgroundJob.job_type == JOB_TYPE_EMBED)
        )
        if isinstance(job.payload, dict)
        and job.payload.get("profile_id") == str(profile.profile_id)
        and int(job.payload.get("source_version") or 0) == profile.version
    ]
    if any(job.status in {"queued", "running"} for job in jobs):
        status = "running" if any(job.status == "running" for job in jobs) else "queued"
        return {"status": status, "error_code": None}
    failed = [job for job in jobs if job.status == "failed"]
    if failed and jobs and all(job.status == "failed" for job in jobs):
        return {"status": "failed", "error_code": failed[-1].last_error_code}
    if any(job.status == "succeeded" for job in jobs):
        return {"status": "succeeded", "error_code": None}
    return {"status": "idle", "error_code": None}
