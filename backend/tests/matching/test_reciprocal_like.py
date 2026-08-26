from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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
    seed_ready_item,
)

from ai_dating.app import create_app
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.matching.models import ConversationMember, Like
from ai_dating.matching.service import commit_like
from ai_dating.recommendations.models import (
    RecommendationAction,
    RecommendationBatch,
    RecommendationItem,
)
from ai_dating.safety.lock import canonical_pair
from ai_dating.safety.models import Conversation, Match

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


def _item_id(client: TestClient, auth: dict, profile_id: UUID) -> str:
    body = client.get("/v1/recommendation-batches/current", headers=auth).json()
    return next(
        row["recommendation_item_id"]
        for row in body["items"]
        if row["profile"]["profile_id"] == str(profile_id)
    )


def _impress(client: TestClient, auth: dict, item_id: str) -> None:
    response = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json=SURFACE,
        headers={**auth, **key()},
    )
    assert response.status_code == 200, response.text


def _like(client: TestClient, auth: dict, item_id: str):
    return client.post(
        f"/v1/recommendation-items/{item_id}/feedback",
        json={"action": "like"},
        headers={**auth, **key()},
    )


def test_reciprocal_likes_create_one_match(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, bob_prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    generate_batch(db, bob_profile, bob_prefs)
    alice_auth = auth_headers(db, alice.account_id)
    bob_auth = auth_headers(db, bob.account_id)
    alice_item = _item_id(client, alice_auth, bob_profile.profile_id)
    bob_item = _item_id(client, bob_auth, alice_profile.profile_id)
    _impress(client, alice_auth, alice_item)
    _impress(client, bob_auth, bob_item)
    first = _like(client, alice_auth, alice_item)
    assert first.status_code == 200
    assert first.json()["match"] is None
    second = _like(client, bob_auth, bob_item)
    assert second.status_code == 200
    match = second.json()["match"]
    assert match["match_id"]
    assert match["conversation_id"]
    replay = _like(client, bob_auth, bob_item)
    assert replay.status_code == 200
    assert replay.json()["match"]["match_id"] == match["match_id"]
    db.expire_all()
    low, high = canonical_pair(alice.account_id, bob.account_id)
    pair_match = db.scalar(
        select(Match).where(Match.account_low_id == low, Match.account_high_id == high)
    )
    assert pair_match is not None
    conversation = db.scalar(
        select(Conversation).where(Conversation.match_id == pair_match.match_id)
    )
    assert conversation is not None
    likes = db.scalar(
        select(func.count())
        .select_from(Like)
        .where(Like.actor_account_id.in_((alice.account_id, bob.account_id)))
    )
    assert likes == 2
    members = db.scalar(
        select(func.count())
        .select_from(ConversationMember)
        .where(ConversationMember.conversation_id == conversation.conversation_id)
    )
    assert members == 2
    match_events = [
        row
        for row in db.scalars(
            select(OutboxEvent).where(OutboxEvent.event_name == "match")
        )
        if row.payload.get("match_id") == str(pair_match.match_id)
    ]
    assert len(match_events) == 1
    like_events = [
        row
        for row in db.scalars(
            select(OutboxEvent).where(OutboxEvent.event_name == "like")
        )
        if row.payload.get("recommendation_item_id") in {alice_item, bob_item}
    ]
    flags = sorted(
        row.payload["properties"]["is_reciprocal_at_commit"] for row in like_events
    )
    assert flags == [False, True]


def test_like_existing_pair_is_idempotent(db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _bob_prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    item = db.scalar(
        select(RecommendationItem).where(
            RecommendationItem.candidate_account_id == bob.account_id
        )
    )
    assert item is not None
    extra = seed_ready_item(db, alice, bob, bob_profile)
    now = datetime.now(UTC)
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
            subject_account_id=bob.account_id,
            recommendation_item_id=extra.recommendation_item_id,
            recommendation_action_id=action.action_id,
            state="active",
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()
    batch = db.get(RecommendationBatch, item.recommendation_batch_id)
    assert batch is not None
    body = commit_like(db, alice, batch, item, now)
    assert body["decision"] == "like"
    assert (
        db.scalar(
            select(func.count())
            .select_from(Like)
            .where(
                Like.actor_account_id == alice.account_id,
                Like.subject_account_id == bob.account_id,
            )
        )
        == 1
    )


@pytest.mark.integration
def test_concurrent_reciprocal_likes_one_match(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, bob_prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    generate_batch(db, bob_profile, bob_prefs)
    alice_auth = auth_headers(db, alice.account_id)
    bob_auth = auth_headers(db, bob.account_id)
    alice_item = _item_id(client, alice_auth, bob_profile.profile_id)
    bob_item = _item_id(client, bob_auth, alice_profile.profile_id)
    _impress(client, alice_auth, alice_item)
    _impress(client, bob_auth, bob_item)

    def worker(auth: dict, item_id: str):
        return _like(client, auth, item_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda pair: worker(*pair),
                ((alice_auth, alice_item), (bob_auth, bob_item)),
            )
        )
    assert {row.status_code for row in results} == {200}
    matches = [row.json()["match"] for row in results if row.json()["match"]]
    assert len(matches) == 1
    db.expire_all()
    low, high = canonical_pair(alice.account_id, bob.account_id)
    pair_match = db.scalar(
        select(Match).where(Match.account_low_id == low, Match.account_high_id == high)
    )
    assert pair_match is not None
    assert (
        db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.match_id == pair_match.match_id)
        )
        == 1
    )
    assert (
        len(
            [
                row
                for row in db.scalars(
                    select(OutboxEvent).where(OutboxEvent.event_name == "match")
                )
                if row.payload.get("match_id") == str(pair_match.match_id)
            ]
        )
        == 1
    )
