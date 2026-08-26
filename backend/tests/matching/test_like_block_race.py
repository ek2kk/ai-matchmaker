from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.onboarding.helpers import key
from tests.recommendations.helpers import auth_headers, generate_batch, seed_pair

from ai_dating.accounts.models import Account
from ai_dating.app import create_app
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.safety.lock import canonical_pair
from ai_dating.safety.models import Match
from ai_dating.safety.service import create_block

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


@pytest.mark.integration
def test_block_and_like_leave_no_active_match(client: TestClient, db: Session):
    (alice, alice_profile, alice_prefs), (bob, bob_profile, _prefs) = seed_pair(db)
    db.commit()
    generate_batch(db, alice_profile, alice_prefs)
    alice_auth = auth_headers(db, alice.account_id)
    current = client.get("/v1/recommendation-batches/current", headers=alice_auth)
    item_id = next(
        row["recommendation_item_id"]
        for row in current.json()["items"]
        if row["profile"]["profile_id"] == str(bob_profile.profile_id)
    )
    impressed = client.post(
        f"/v1/recommendation-items/{item_id}/impression",
        json=SURFACE,
        headers={**alice_auth, **key()},
    )
    assert impressed.status_code == 200
    alice_id = alice.account_id
    bob_pid = bob_profile.profile_id
    engine = db.get_bind()

    def like_worker() -> int:
        return client.post(
            f"/v1/recommendation-items/{item_id}/feedback",
            json={"action": "like"},
            headers={**alice_auth, **key()},
        ).status_code

    def block_worker() -> None:
        with Session(engine) as session:
            actor = session.get(Account, alice_id)
            assert actor is not None
            create_block(
                session,
                actor,
                profile_id=bob_pid,
                match_id=None,
                reason_code="spam",
            )
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        like_fut = pool.submit(like_worker)
        block_fut = pool.submit(block_worker)
        like_status = like_fut.result()
        block_fut.result()
    assert like_status in {200, 404}
    db.expire_all()
    low, high = canonical_pair(alice_id, bob.account_id)
    pair_match = db.scalar(
        select(Match).where(Match.account_low_id == low, Match.account_high_id == high)
    )
    assert pair_match is None or pair_match.state != "active"
