from sqlalchemy.orm import Session

from ai_dating.ai.schema import JOB_TYPE_EMBED, JOB_TYPE_EXTRACT
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.claim import claim_jobs
from ai_dating.jobs.embed import process_embed_job
from ai_dating.jobs.extract_facts import process_extract_job, run_once
from ai_dating.jobs.generate_batch import process_generate_job
from ai_dating.jobs.moderate_message import process_moderate_message_job
from ai_dating.jobs.process_photo import cleanup_media_job, process_photo_job
from ai_dating.media.constants import JOB_TYPE_CLEANUP_MEDIA, JOB_TYPE_PROCESS_PHOTO
from ai_dating.messaging.constants import JOB_TYPE_MODERATE_MESSAGE
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE


def drain_extraction() -> None:
    settings = load_settings()
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        jobs = claim_jobs(
            session,
            limit=20,
            lease_seconds=settings.job_lease_seconds,
            job_types=(JOB_TYPE_EXTRACT,),
        )
    if not jobs:
        return
    with Session(engine) as session:
        run_once(session, settings, jobs)


def drain_jobs() -> None:
    settings = load_settings()
    engine = create_sync_engine(settings)
    for _ in range(8):
        with Session(engine) as session:
            jobs = claim_jobs(
                session, limit=20, lease_seconds=settings.job_lease_seconds
            )
        if not jobs:
            return
        with Session(engine) as session:
            for job in jobs:
                if job.job_type == JOB_TYPE_EXTRACT:
                    process_extract_job(session, settings, job)
                elif job.job_type == JOB_TYPE_EMBED:
                    process_embed_job(session, settings, job)
                elif job.job_type == JOB_TYPE_GENERATE:
                    process_generate_job(session, settings, job)
                elif job.job_type == JOB_TYPE_PROCESS_PHOTO:
                    process_photo_job(session, settings, job)
                elif job.job_type == JOB_TYPE_CLEANUP_MEDIA:
                    cleanup_media_job(session, settings, job)
                elif job.job_type == JOB_TYPE_MODERATE_MESSAGE:
                    process_moderate_message_job(session, settings, job)
