from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from tests.recommendations.helpers import seed_person

from ai_dating.ai.schema import PROJECTION_SCHEMA_VERSION
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.jobs.claim import claim_jobs
from ai_dating.jobs.generate_batch import process_generate_job
from ai_dating.privacy.models import BackgroundJob
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE, POLICY_VERSION
from ai_dating.recommendations.eligibility import current_embeddings
from ai_dating.recommendations.enqueue import enqueue_generation, generation_key
from ai_dating.recommendations.models import RecommendationBatch, RecommendationItem
from ai_dating.recommendations.ranking import cosine_similarity

pytestmark = [pytest.mark.postgres, pytest.mark.integration]


@pytest.fixture
def db():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        yield session
        session.rollback()


def _run(db: Session, settings=None) -> None:
    settings = settings or load_settings()
    jobs = claim_jobs(
        db,
        limit=8,
        lease_seconds=settings.job_lease_seconds,
        job_types=(JOB_TYPE_GENERATE,),
    )
    with Session(db.get_bind()) as work:
        for job in jobs:
            process_generate_job(work, settings, job)


def test_generation_persists_at_most_five_and_emits_event(db: Session):
    settings = load_settings()
    actor_acc, actor_profile, actor_prefs = seed_person(db, gender="woman")
    for index in range(6):
        seed_person(
            db,
            gender="man",
            accepted=["woman"],
            lat=55.75 + index * 0.001,
        )
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    job_id = enqueue_generation(
        db,
        profile=actor_profile,
        prefs=actor_prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    assert job_id is not None
    db.commit()
    _run(db, settings)
    with Session(db.get_bind()) as session:
        batch = session.scalar(
            select(RecommendationBatch).where(
                RecommendationBatch.owner_account_id == actor_acc.account_id
            )
        )
        assert batch is not None
        assert batch.item_count <= 5
        items = list(
            session.scalars(
                select(RecommendationItem).where(
                    RecommendationItem.recommendation_batch_id
                    == batch.recommendation_batch_id
                )
            )
        )
        assert 1 <= len(items) <= 5
        assert {item.rank for item in items} == set(range(1, len(items) + 1))
        events = [
            row
            for row in session.scalars(select(OutboxEvent))
            if row.event_name == "recommendation_generation_queued"
            and row.payload["properties"]["job_id"] == str(job_id)
        ]
        assert len(events) == 1
        assert "missing_gates" not in batch.input_snapshot
        assert batch.input_snapshot["policy_version"] == POLICY_VERSION
        assert batch.eligibility_version == POLICY_VERSION
        second = enqueue_generation(
            session,
            profile=actor_profile,
            prefs=actor_prefs,
            now=now,
            trigger_code="onboarding_complete",
        )
        assert second is not None
        assert (
            enqueue_generation(
                session,
                profile=actor_profile,
                prefs=actor_prefs,
                now=now,
                trigger_code="onboarding_complete",
            )
            is None
        )


def test_duplicate_processing_is_idempotent(db: Session):
    settings = load_settings()
    _actor_acc, actor_profile, actor_prefs = seed_person(db, gender="woman")
    seed_person(db, gender="man", accepted=["woman"])
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    enqueue_generation(
        db,
        profile=actor_profile,
        prefs=actor_prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    db.commit()
    _run(db, settings)
    _run(db, settings)
    with Session(db.get_bind()) as session:
        batches = list(
            session.scalars(
                select(RecommendationBatch).where(
                    RecommendationBatch.generation_key
                    == generation_key(
                        actor_profile.account_id,
                        actor_profile.version,
                        actor_prefs.version,
                        now=now,
                        quota_slot=0,
                    )
                )
            )
        )
        assert len(batches) == 1


def test_source_drift_discards_and_requeues(db: Session):
    settings = load_settings()
    _actor_acc, actor_profile, actor_prefs = seed_person(db, gender="woman")
    seed_person(db, gender="man", accepted=["woman"])
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    enqueue_generation(
        db,
        profile=actor_profile,
        prefs=actor_prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    db.commit()
    jobs = claim_jobs(
        db,
        limit=1,
        lease_seconds=settings.job_lease_seconds,
        job_types=(JOB_TYPE_GENERATE,),
    )
    actor_profile.version += 1
    db.commit()
    with Session(db.get_bind()) as work:
        process_generate_job(work, settings, jobs[0])
    with Session(db.get_bind()) as session:
        original = session.get(BackgroundJob, jobs[0].job_id)
        assert original is not None
        assert original.status == "succeeded"
        assert original.last_error_code == "stale"
        queued = list(
            session.scalars(
                select(BackgroundJob).where(
                    BackgroundJob.job_type == JOB_TYPE_GENERATE,
                    BackgroundJob.status == "queued",
                )
            )
        )
        assert queued
        assert queued[-1].payload["profile_version"] == actor_profile.version
        assert queued[-1].payload["policy_version"] == POLICY_VERSION


def test_current_embedding_and_sql_cosine_match_python(db: Session):
    _actor_acc, actor_profile, _prefs = seed_person(db, gender="woman")
    _cand_acc, cand_profile, _cand_prefs = seed_person(
        db, gender="man", accepted=["woman"]
    )
    found = current_embeddings(
        db,
        [
            (actor_profile.profile_id, 1, "desired_partner"),
            (cand_profile.profile_id, 1, "self"),
        ],
        model_version="gte-base",
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
    )
    desired = found[(actor_profile.profile_id, "desired_partner")]
    self_row = found[(cand_profile.profile_id, "self")]
    python_sim = cosine_similarity(desired.embedding, self_row.embedding)
    assert python_sim is not None
    distance = db.execute(
        text(
            "SELECT e.embedding <=> d.embedding "
            "FROM profile_embeddings e, profile_embeddings d "
            "WHERE e.embedding_id = :e AND d.embedding_id = :d"
        ),
        {"e": self_row.embedding_id, "d": desired.embedding_id},
    ).scalar()
    assert abs((1.0 - float(distance)) - python_sim) < 1e-5
