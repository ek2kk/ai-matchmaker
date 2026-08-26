from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.recommendations.helpers import seed_person

from ai_dating.app import create_app
from ai_dating.auth.sessions import issue_session
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.jobs.claim import claim_jobs
from ai_dating.jobs.generate_batch import process_generate_job
from ai_dating.profiles.models import Profile
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE
from ai_dating.recommendations.enqueue import enqueue_generation
from ai_dating.recommendations.models import RecommendationBatch

pytestmark = [pytest.mark.postgres]


@pytest.fixture
def db():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        yield session
        session.commit()


@pytest.fixture
def client():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return TestClient(create_app(settings))


def _auth(db: Session, account_id) -> dict[str, str]:
    token, _sess = issue_session(db, account_id, 86400)
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def _generate(db: Session, profile, prefs) -> None:
    now = datetime.now(UTC)
    enqueue_generation(
        db,
        profile=profile,
        prefs=prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    db.commit()
    settings = load_settings()
    jobs = claim_jobs(
        db,
        limit=8,
        lease_seconds=settings.job_lease_seconds,
        job_types=(JOB_TYPE_GENERATE,),
    )
    with Session(db.get_bind()) as work:
        for job in jobs:
            process_generate_job(work, settings, job)


def test_current_requires_auth(client: TestClient):
    assert client.get("/v1/recommendation-batches/current").status_code == 401


def test_current_returns_public_cards_without_scores(client: TestClient, db: Session):
    actor_acc, actor_profile, actor_prefs = seed_person(
        db, gender="woman", last_active=datetime.now(UTC)
    )
    seed_person(db, gender="man", accepted=["woman"], last_active=datetime.now(UTC))
    seed_person(db, gender="man", accepted=["woman"], last_active=datetime.now(UTC))
    db.commit()
    _generate(db, actor_profile, actor_prefs)
    auth = _auth(db, actor_acc.account_id)
    response = client.get("/v1/recommendation-batches/current", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "insufficient_supply"}
    assert 1 <= len(body["items"]) <= 5
    for item in body["items"]:
        assert "final_score" not in item
        assert "candidate_account_id" not in item
        profile = item["profile"]
        assert profile["profile_id"]
        assert profile["display_name"]
        assert "date_of_birth" not in profile
        assert "location" not in profile
        assert "account_id" not in profile
        assert "photo_urls" in profile


def test_current_omits_now_ineligible_candidate(client: TestClient, db: Session):
    actor_acc, actor_profile, actor_prefs = seed_person(
        db, gender="woman", last_active=datetime.now(UTC)
    )
    seed_person(db, gender="man", accepted=["woman"], last_active=datetime.now(UTC))
    db.commit()
    _generate(db, actor_profile, actor_prefs)
    auth = _auth(db, actor_acc.account_id)
    first = client.get("/v1/recommendation-batches/current", headers=auth)
    assert first.status_code == 200
    items = first.json()["items"]
    assert items
    hidden_id = UUID(items[0]["profile"]["profile_id"])
    row = db.get(Profile, hidden_id)
    assert row is not None
    row.visibility = "hidden"
    db.commit()
    again = client.get("/v1/recommendation-batches/current", headers=auth)
    assert again.status_code == 200
    left = {item["profile"]["profile_id"] for item in again.json()["items"]}
    assert str(hidden_id) not in left


def test_current_pending_when_no_batch(client: TestClient, db: Session):
    actor_acc, _profile, _prefs = seed_person(
        db, gender="woman", last_active=datetime.now(UTC)
    )
    db.commit()
    auth = _auth(db, actor_acc.account_id)
    response = client.get("/v1/recommendation-batches/current", headers=auth)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"


def test_empty_batch_rebuilds_when_supply_appears(db: Session):
    now = datetime.now(UTC)
    lat = 70.0 + (uuid4().int % 10_000) / 10_000.0
    lon = 20.0 + (uuid4().int % 10_000) / 10_000.0
    actor_acc, actor_profile, actor_prefs = seed_person(
        db,
        gender="woman",
        search_mode="friendship",
        goals=[],
        age_min=40,
        age_max=45,
        lat=lat,
        lon=lon,
        max_distance_km=5,
        last_active=now,
    )
    db.commit()
    _generate(db, actor_profile, actor_prefs)
    with Session(db.get_bind()) as session:
        batch = session.scalar(
            select(RecommendationBatch).where(
                RecommendationBatch.owner_account_id == actor_acc.account_id
            )
        )
        assert batch is not None
        assert batch.item_count == 0
    seed_person(
        db,
        gender="man",
        accepted=["woman"],
        search_mode="friendship",
        goals=[],
        dob_year=1984,
        lat=lat,
        lon=lon,
        max_distance_km=5,
        last_active=now,
    )
    db.commit()
    job_id = enqueue_generation(
        db,
        profile=actor_profile,
        prefs=actor_prefs,
        now=now,
        trigger_code="refill",
    )
    assert job_id is not None
    db.commit()
    settings = load_settings()
    jobs = claim_jobs(
        db,
        limit=8,
        lease_seconds=settings.job_lease_seconds,
        job_types=(JOB_TYPE_GENERATE,),
    )
    with Session(db.get_bind()) as work:
        for job in jobs:
            process_generate_job(work, settings, job)
    with Session(db.get_bind()) as session:
        batch = session.scalar(
            select(RecommendationBatch)
            .where(RecommendationBatch.owner_account_id == actor_acc.account_id)
            .order_by(RecommendationBatch.ready_at.desc())
        )
        assert batch is not None
        assert batch.item_count >= 1
