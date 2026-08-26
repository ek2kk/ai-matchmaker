from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.profiles.models import Profile
from tests.onboarding.helpers import account, auth_of, profile_body


def test_register_creates_hidden_draft_profile(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    empty = client.get("/v1/onboarding", headers=auth).json()
    assert empty["profile"]["version"] == 0
    assert empty["privacy"]["discoverable"] is False
    created = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert created.status_code == 200
    body = created.json()
    assert body["visibility"] == "hidden"
    assert body["moderation_state"] == "pending"
    assert body["activated_at"] is None
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        row = session.scalar(
            select(Profile).where(Profile.account_id == acc["account_id"])
        )
        assert row is not None
        assert row.visibility == "hidden"
