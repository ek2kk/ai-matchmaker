from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION
from tests.ai.helpers import drain_extraction
from tests.onboarding.helpers import (
    account,
    auth_of,
    key,
    prefs_body,
    profile_body,
    prompt_answers,
)


def _grant(client: TestClient, auth: dict, purpose: str) -> None:
    response = client.post(
        "/v1/consents",
        json={
            "purpose": purpose,
            "policy_version": PRIVACY_POLICY_VERSION,
            "decision": "granted",
        },
        headers={**auth, **key()},
    )
    assert response.status_code == 200


def _finish_user_gates(client: TestClient, auth: dict) -> tuple[int, int]:
    profile = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert profile.status_code == 200
    prefs = client.patch("/v1/onboarding/preferences", json=prefs_body(0), headers=auth)
    assert prefs.status_code == 200
    _grant(client, auth, "terms_privacy")
    _grant(client, auth, "ai_matching")
    privacy = client.get("/v1/privacy", headers=auth).json()
    visible = client.patch(
        "/v1/privacy",
        json={"expected_version": privacy["version"], "discoverable": True},
        headers=auth,
    )
    assert visible.status_code == 200
    answer = client.patch(
        "/v1/profile",
        json={
            "expected_version": profile.json()["version"],
            "answers": prompt_answers(),
        },
        headers=auth,
    )
    assert answer.status_code == 200
    drain_extraction()
    pending = client.get("/v1/profile/facts?state=pending", headers=auth).json()[
        "items"
    ]
    for item in pending:
        reviewed = client.post(
            f"/v1/profile/facts/{item['fact_id']}/review",
            json={
                "decision": "accept",
                "expected_source_version": item["source_version"],
            },
            headers={**auth, **key()},
        )
        assert reviewed.status_code == 200
    session = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    )
    assert session.status_code == 200
    skipped = client.post(
        f"/v1/onboarding/calibration-sessions/{session.json()['calibration_session_id']}/complete",
        json={"decision": "skip"},
        headers={**auth, **key()},
    )
    assert skipped.status_code == 200
    latest = client.get("/v1/onboarding", headers=auth).json()
    return latest["profile"]["version"], prefs.json()["version"]


def test_complete_returns_202_activation_pending(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile_version, prefs_version = _finish_user_gates(client, auth)
    done = client.post(
        "/v1/onboarding/complete",
        json={
            "expected_profile_version": profile_version,
            "expected_preferences_version": prefs_version,
        },
        headers={**auth, **key()},
    )
    assert done.status_code == 202
    body = done.json()
    assert body["status"] == "profile_activation_pending"
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["onboarding_completed"] is True
    assert state["profile"]["visibility"] == "hidden"
    assert state["profile"]["moderation_state"] == "pending"
    assert state["profile"]["activated_at"] is None


def test_prompt_answer_requires_both_sides(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert profile.status_code == 200
    client.patch(
        "/v1/profile",
        json={
            "expected_version": profile.json()["version"],
            "answers": [{"prompt_code": "self_about", "answer_text": "I like travel."}],
        },
        headers=auth,
    )
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["gates"]["prompt_answer"] is False
    latest = client.get("/v1/onboarding", headers=auth).json()
    client.patch(
        "/v1/profile",
        json={
            "expected_version": latest["profile"]["version"],
            "answers": [
                {
                    "prompt_code": "partner_who",
                    "answer_text": "Someone who likes travel.",
                }
            ],
        },
        headers=auth,
    )
    again = client.get("/v1/onboarding", headers=auth).json()
    assert again["gates"]["prompt_answer"] is True


def test_complete_missing_gate_422_not_202(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    response = client.post(
        "/v1/onboarding/complete",
        json={"expected_profile_version": 1, "expected_preferences_version": 0},
        headers={**auth, **key()},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_complete_idempotent_same_key(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile_version, prefs_version = _finish_user_gates(client, auth)
    headers = {**auth, **key()}
    payload = {
        "expected_profile_version": profile_version,
        "expected_preferences_version": prefs_version,
    }
    first = client.post("/v1/onboarding/complete", json=payload, headers=headers)
    second = client.post("/v1/onboarding/complete", json=payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["status"] == second.json()["status"]
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        events = [
            row
            for row in session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_name == "onboarding_completed"
                )
            )
            if row.payload.get("actor_account_id") == acc["account_id"]
        ]
        assert len(events) == 1
        raw = str(events[0].payload)
        assert "I like travel" not in raw
        assert "Alex" not in raw


def test_complete_sets_onboarding_completed_at_and_active_status(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile_version, prefs_version = _finish_user_gates(client, auth)
    client.post(
        "/v1/onboarding/complete",
        json={
            "expected_profile_version": profile_version,
            "expected_preferences_version": prefs_version,
        },
        headers={**auth, **key()},
    )
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        row = session.get(Account, acc["account_id"])
        assert row is not None
        assert row.status == "active"
        assert row.onboarding_completed_at is not None
