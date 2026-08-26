from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.onboarding.helpers import key
from tests.recommendations.helpers import (
    auth_headers,
    generate_batch,
    seed_pair,
    seed_person,
    seed_ready_item,
)

from ai_dating.app import create_app
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.recommendations.models import RecommendationExposure

pytestmark = [pytest.mark.postgres]
SURFACE = {"surface": "daily_batch"}


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


def _events(db: Session, name: str, item_id: UUID) -> int:
    return sum(
        1
        for row in db.scalars(select(OutboxEvent).where(OutboxEvent.event_name == name))
        if row.payload.get("recommendation_item_id") == str(item_id)
    )


def test_impression_requires_auth(client: TestClient):
    response = client.post(
        f"/v1/recommendation-items/{uuid4()}/impression",
        json=SURFACE,
        headers=key(),
    )
    assert response.status_code == 401


def test_impression_idempotent_hides_ids(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    auth = auth_headers(db, alice.account_id)
    current = client.get("/v1/recommendation-batches/current", headers=auth)
    assert current.status_code == 200
    item = next(
        row
        for row in current.json()["items"]
        if row["profile"]["profile_id"] == str(bob_profile.profile_id)
    )
    item_id = item["recommendation_item_id"]
    first = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["recommendation_item_id"] == item_id
    assert "candidate_account_id" not in body
    assert "actor_account_id" not in body
    again = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert again.status_code == 200
    assert again.json()["exposure_id"] == body["exposure_id"]
    db.expire_all()
    assert _events(db, "impression", UUID(item_id)) == 1
    count = db.scalar(
        select(func.count())
        .select_from(RecommendationExposure)
        .where(RecommendationExposure.owner_account_id == alice.account_id)
    )
    assert count == 1


def test_impression_conflict_for_other_item(client: TestClient, db: Session):
    (alice, _ap, _apr), (bob, bob_profile, _bp) = seed_pair(db)
    first = seed_ready_item(db, alice, bob, bob_profile)
    second = seed_ready_item(db, alice, bob, bob_profile)
    db.commit()
    auth = auth_headers(db, alice.account_id)
    ok = client.post(
        f"/v1/recommendation-items/{first.recommendation_item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert ok.status_code == 200
    conflict = client.post(
        f"/v1/recommendation-items/{second.recommendation_item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "already_exposed_elsewhere"


def test_open_requires_impression_and_is_idempotent(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    auth = auth_headers(db, alice.account_id)
    current = client.get("/v1/recommendation-batches/current", headers=auth)
    item_id = next(
        row["recommendation_item_id"]
        for row in current.json()["items"]
        if row["profile"]["profile_id"] == str(bob_profile.profile_id)
    )
    missing = client.post(
        f"/v1/recommendation-items/{item_id}/open",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert missing.status_code == 404
    assert (
        client.post(
            f"/v1/recommendation-items/{item_id}/impression",
            json=SURFACE,
            headers={**auth, **key()},
        ).status_code
        == 200
    )
    first = client.post(
        f"/v1/recommendation-items/{item_id}/open",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert first.status_code == 200
    again = client.post(
        f"/v1/recommendation-items/{item_id}/open",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert again.status_code == 200
    assert again.json()["action_id"] == first.json()["action_id"]
    db.expire_all()
    assert _events(db, "open", UUID(item_id)) == 1


def test_idor_and_unknown_fields(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, bob_prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    generate_batch(db, bob_profile, bob_prefs)
    alice_auth = auth_headers(db, alice.account_id)
    bob_auth = auth_headers(db, bob.account_id)
    item_id = next(
        row["recommendation_item_id"]
        for row in client.get(
            "/v1/recommendation-batches/current", headers=alice_auth
        ).json()["items"]
        if row["profile"]["profile_id"] == str(bob_profile.profile_id)
    )
    stolen = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json=SURFACE,
        headers={**bob_auth, **key()},
    )
    assert stolen.status_code == 404
    extra = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json={"surface": "daily_batch", "actor_account_id": str(alice.account_id)},
        headers={**alice_auth, **key()},
    )
    assert extra.status_code == 422


def test_pass_reason_and_terminal_conflict(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    auth = auth_headers(db, alice.account_id)
    current = client.get("/v1/recommendation-batches/current", headers=auth)
    item_id = next(
        row["recommendation_item_id"]
        for row in current.json()["items"]
        if row["profile"]["profile_id"] == str(bob_profile.profile_id)
    )
    assert (
        client.post(
            f"/v1/recommendation-items/{item_id}/impression",
            json=SURFACE,
            headers={**auth, **key()},
        ).status_code
        == 200
    )
    bad = client.post(
        f"/v1/recommendation-items/{item_id}/feedback",
        json={"action": "pass", "reason_code": "harassment"},
        headers={**auth, **key()},
    )
    assert bad.status_code == 422
    passed = client.post(
        f"/v1/recommendation-items/{item_id}/feedback",
        json={"action": "pass", "reason_code": "photos"},
        headers={**auth, **key()},
    )
    assert passed.status_code == 200
    assert passed.json()["decision"] == "pass"
    assert passed.json()["match"] is None
    conflict = client.post(
        f"/v1/recommendation-items/{item_id}/feedback",
        json={"action": "like"},
        headers={**auth, **key()},
    )
    assert conflict.status_code == 409
    replay = client.post(
        f"/v1/recommendation-items/{item_id}/feedback",
        json={"action": "pass", "reason_code": "photos"},
        headers={**auth, **key()},
    )
    assert replay.status_code == 200
    assert replay.json()["action_id"] == passed.json()["action_id"]
    db.expire_all()
    assert _events(db, "pass", UUID(item_id)) == 1
    assert _events(db, "pass_reason", UUID(item_id)) == 1
    current = client.get("/v1/recommendation-batches/current", headers=auth)
    shown = next(
        row
        for row in current.json()["items"]
        if row["recommendation_item_id"] == item_id
    )
    assert shown["decision"] == "pass"


def test_stale_candidate_is_404(client: TestClient, db: Session):
    (alice, _ap, _apr), (bob, bob_profile, _bp) = seed_pair(db)
    item = seed_ready_item(db, alice, bob, bob_profile)
    bob_profile.visibility = "hidden"
    db.commit()
    auth = auth_headers(db, alice.account_id)
    response = client.post(
        f"/v1/recommendation-items/{item.recommendation_item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert response.status_code == 404


def test_refresh_after_consumption(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    auth = auth_headers(db, alice.account_id)
    current = client.get("/v1/recommendation-batches/current", headers=auth)
    items = current.json()["items"]
    assert items
    too_soon = client.post(
        "/v1/recommendation-batches/current/refresh",
        json={},
        headers={**auth, **key()},
    )
    assert too_soon.status_code == 409
    for row in items:
        item_id = row["recommendation_item_id"]
        assert (
            client.post(
                f"/v1/recommendation-items/{item_id}/impression",
                json=SURFACE,
                headers={**auth, **key()},
            ).status_code
            == 200
        )
        passed = client.post(
            f"/v1/recommendation-items/{item_id}/feedback",
            json={"action": "pass"},
            headers={**auth, **key()},
        )
        assert passed.status_code == 200
    refreshed = client.post(
        "/v1/recommendation-batches/current/refresh",
        json={},
        headers={**auth, **key()},
    )
    assert refreshed.status_code == 202
    assert refreshed.json()["status"] == "pending"


def test_refresh_when_remaining_item_already_liked(client: TestClient, db: Session):
    from datetime import UTC, datetime, timedelta

    from ai_dating.matching.models import Like
    from ai_dating.recommendations.models import (
        RecommendationAction,
        RecommendationBatch,
        RecommendationItem,
    )

    now = datetime.now(UTC)
    alice, alice_profile, alice_prefs = seed_person(
        db, gender="woman", last_active=now, lat=61.12, lon=29.73
    )
    _bob, _bob_profile, _bp = seed_person(
        db,
        gender="man",
        accepted=["woman"],
        last_active=now,
        lat=61.12,
        lon=29.73,
    )
    carol, carol_profile, _cp = seed_person(
        db,
        gender="man",
        accepted=["woman"],
        last_active=now,
        lat=61.12,
        lon=29.73,
    )
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    extra = seed_ready_item(db, alice, carol, carol_profile)
    extra_batch = db.get(RecommendationBatch, extra.recommendation_batch_id)
    assert extra_batch is not None
    extra_batch.expires_at = now - timedelta(hours=1)
    action = RecommendationAction(
        action_id=uuid4(),
        recommendation_item_id=extra.recommendation_item_id,
        actor_account_id=alice.account_id,
        action="like",
        reason_code=None,
        created_at=now,
    )
    db.add(action)
    db.flush()
    db.add(
        Like(
            like_id=uuid4(),
            actor_account_id=alice.account_id,
            subject_account_id=carol.account_id,
            recommendation_item_id=extra.recommendation_item_id,
            recommendation_action_id=action.action_id,
            state="active",
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    auth = auth_headers(db, alice.account_id)
    batch = db.scalar(
        select(RecommendationBatch)
        .where(
            RecommendationBatch.owner_account_id == alice.account_id,
            RecommendationBatch.generation_key.like(f"{alice.account_id}:%"),
        )
        .order_by(RecommendationBatch.ready_at.desc())
    )
    assert batch is not None
    items = list(
        db.scalars(
            select(RecommendationItem).where(
                RecommendationItem.recommendation_batch_id
                == batch.recommendation_batch_id
            )
        )
    )
    assert any(item.candidate_account_id == carol.account_id for item in items)
    for item in items:
        if item.candidate_account_id == carol.account_id:
            continue
        item_id = str(item.recommendation_item_id)
        assert (
            client.post(
                f"/v1/recommendation-items/{item_id}/impression",
                json=SURFACE,
                headers={**auth, **key()},
            ).status_code
            == 200
        )
        passed = client.post(
            f"/v1/recommendation-items/{item_id}/feedback",
            json={"action": "pass"},
            headers={**auth, **key()},
        )
        assert passed.status_code == 200
    refreshed = client.post(
        "/v1/recommendation-batches/current/refresh",
        json={},
        headers={**auth, **key()},
    )
    assert refreshed.status_code == 202, refreshed.text
