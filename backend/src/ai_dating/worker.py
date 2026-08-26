from __future__ import annotations

import signal
import time

import structlog
from sqlalchemy.orm import Session

from ai_dating.ai.schema import JOB_TYPE_EMBED, JOB_TYPE_EXTRACT
from ai_dating.config import load_settings, require_startup
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.claim import claim_jobs
from ai_dating.jobs.embed import process_embed_job
from ai_dating.jobs.extract_facts import process_extract_job
from ai_dating.jobs.generate_batch import process_generate_job
from ai_dating.jobs.moderate_message import process_moderate_message_job
from ai_dating.jobs.process_photo import cleanup_media_job, process_photo_job
from ai_dating.logging import configure_logging
from ai_dating.media.constants import JOB_TYPE_CLEANUP_MEDIA, JOB_TYPE_PROCESS_PHOTO
from ai_dating.messaging.constants import JOB_TYPE_MODERATE_MESSAGE
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE

log = structlog.get_logger("ai_dating.worker")
_stop = False


def _handle_stop(_signum: int, _frame: object) -> None:
    global _stop
    _stop = True


def main() -> None:
    settings = load_settings()
    require_startup(settings)
    configure_logging(settings, service_process="worker")
    if not settings.database_url and not settings.database_direct_url:
        raise SystemExit("DATABASE_URL is required for the worker")
    engine = create_sync_engine(settings)
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    while not _stop:
        with Session(engine) as claim_session:
            jobs = claim_jobs(
                claim_session,
                limit=8,
                lease_seconds=settings.job_lease_seconds,
            )
        if jobs:
            with Session(engine) as work_session:
                for job in jobs:
                    if job.job_type == JOB_TYPE_EXTRACT:
                        process_extract_job(work_session, settings, job)
                    elif job.job_type == JOB_TYPE_EMBED:
                        process_embed_job(work_session, settings, job)
                    elif job.job_type == JOB_TYPE_GENERATE:
                        process_generate_job(work_session, settings, job)
                    elif job.job_type == JOB_TYPE_PROCESS_PHOTO:
                        process_photo_job(work_session, settings, job)
                    elif job.job_type == JOB_TYPE_CLEANUP_MEDIA:
                        cleanup_media_job(work_session, settings, job)
                    elif job.job_type == JOB_TYPE_MODERATE_MESSAGE:
                        process_moderate_message_job(work_session, settings, job)
        if _stop:
            break
        time.sleep(settings.worker_poll_seconds)
    log.info("worker_shutdown")
