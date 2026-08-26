from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.onboarding.helpers import account, auth_of, key, profile_body

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.onboarding.calibration import PAIR_IDS, create_session
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION


def _grant(
    client: TestClient, auth: dict, purpose: str, decision: str = "granted"
) -> None:
    response = client.post(
        "/v1/consents",
        json={
            "purpose": purpose,
            "policy_version": PRIVACY_POLICY_VERSION,
            "decision": decision,
        },
        headers={**auth, **key()},
    )
    assert response.status_code == 200


def test_create_session_is_idempotent_across_keys(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    first = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    )
    second = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["calibration_session_id"]
        == second.json()["calibration_session_id"]
    )


def test_create_session_is_race_safe(client: TestClient):
    acc = account(client)
    account_id = UUID(acc["account_id"])
    engine = create_sync_engine(load_settings())
    now = datetime.now(UTC)

    def worker() -> str:
        with Session(engine) as db:
            row = db.get(Account, account_id)
            view = create_session(db, row, now)
            db.commit()
            return view["calibration_session_id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker)
        second = pool.submit(worker)
        ids = [first.result(), second.result()]
    assert ids[0] == ids[1]


def test_session_uses_demo_ids_only(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    created = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    )
    assert created.status_code == 200
    body = created.json()
    assert body["synthetic_only"] is True
    assert len(body["pairs"]) == 5
    for pair in body["pairs"]:
        assert pair["demo_pair_id"].startswith("demo-v1-")
        assert pair["left"]["demo_id"].startswith("demo-v1-")
        assert pair["right"]["demo_id"].startswith("demo-v1-")
        assert pair["label"] == "пример, не реальный участник"


def test_choice_does_not_emit_interaction_events(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    session = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    ).json()
    choice = client.post(
        f"/v1/onboarding/calibration-sessions/{session['calibration_session_id']}/choices",
        json={"demo_pair_id": session["pairs"][0]["demo_pair_id"], "selection": "left"},
        headers={**auth, **key()},
    )
    assert choice.status_code == 200
    engine = create_sync_engine(load_settings())
    with Session(engine) as db:
        names = {
            row.event_name
            for row in db.scalars(select(OutboxEvent))
            if row.payload.get("actor_account_id") == acc["account_id"]
        }
    assert "impression" not in names
    assert "like" not in names
    assert "pass" not in names
    assert "match" not in names


def test_complete_requires_all_pairs_and_consent(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    session = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    ).json()
    sid = session["calibration_session_id"]
    missing = client.post(
        f"/v1/onboarding/calibration-sessions/{sid}/complete",
        json={"decision": "complete"},
        headers={**auth, **key()},
    )
    assert missing.status_code == 422
    for pair_id in PAIR_IDS:
        picked = client.post(
            f"/v1/onboarding/calibration-sessions/{sid}/choices",
            json={"demo_pair_id": pair_id, "selection": "neither"},
            headers={**auth, **key()},
        )
        assert picked.status_code == 200
    still = client.post(
        f"/v1/onboarding/calibration-sessions/{sid}/complete",
        json={"decision": "complete"},
        headers={**auth, **key()},
    )
    assert still.status_code == 422
    _grant(client, auth, "calibration")
    done = client.post(
        f"/v1/onboarding/calibration-sessions/{sid}/complete",
        json={"decision": "complete"},
        headers={**auth, **key()},
    )
    assert done.status_code == 200
    assert done.json()["state"] == "completed"
    engine = create_sync_engine(load_settings())
    with Session(engine) as db:
        events = [
            row
            for row in db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_name == "calibration_completed"
                )
            )
            if row.payload.get("actor_account_id") == acc["account_id"]
        ]
        assert len(events) == 1
        assert events[0].payload["properties"]["skipped"] is False
        assert events[0].payload["properties"]["synthetic_only"] is True


def test_skip_and_consent_clear(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    session = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    ).json()
    sid = session["calibration_session_id"]
    client.post(
        f"/v1/onboarding/calibration-sessions/{sid}/choices",
        json={
            "demo_pair_id": session["pairs"][0]["demo_pair_id"],
            "selection": "right",
        },
        headers={**auth, **key()},
    )
    skipped = client.post(
        f"/v1/onboarding/calibration-sessions/{sid}/complete",
        json={"decision": "skip"},
        headers={**auth, **key()},
    )
    assert skipped.status_code == 200
    assert skipped.json()["state"] == "skipped"
    _grant(client, auth, "calibration")
    _grant(client, auth, "calibration", "withdrawn")
    cleared = client.post(
        "/v1/onboarding/calibration-sessions", json={}, headers={**auth, **key()}
    )
    assert cleared.status_code == 200
    assert cleared.json()["choices"] == []
    assert cleared.json()["state"] == "started"


def test_other_account_session_is_404(client: TestClient):
    owner = account(client)
    session = client.post(
        "/v1/onboarding/calibration-sessions",
        json={},
        headers={**auth_of(owner), **key()},
    ).json()
    other = account(client)
    stolen = client.post(
        f"/v1/onboarding/calibration-sessions/{session['calibration_session_id']}/choices",
        json={"demo_pair_id": session["pairs"][0]["demo_pair_id"], "selection": "left"},
        headers={**auth_of(other), **key()},
    )
    assert stolen.status_code == 404
