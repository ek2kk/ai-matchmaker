from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from tests.onboarding.helpers import account, auth_of, profile_body


def _step_events(account_id: str) -> list[dict]:
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        rows = session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.event_name == "onboarding_step_completed")
            .order_by(OutboxEvent.occurred_at)
        )
        return [
            row.payload
            for row in rows
            if row.payload.get("actor_account_id") == account_id
        ]


def test_step_completed_event_once_per_step(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    first = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert first.status_code == 200
    second = client.patch(
        "/v1/onboarding/profile",
        json={"expected_version": first.json()["version"], "display_name": "Sam"},
        headers=auth,
    )
    assert second.status_code == 200
    events = [
        item
        for item in _step_events(acc["account_id"])
        if item["properties"]["step_code"] == "profile"
    ]
    assert len(events) == 1


def test_events_contain_no_raw_profile_text(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    raw = str(_step_events(acc["account_id"]))
    assert "Alex" not in raw
    assert "55.75" not in raw
    assert "37.62" not in raw
    assert "2000-01-15" not in raw
