from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.app import create_app
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION, BackgroundJob, Consent


@pytest.fixture
def client():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return TestClient(create_app(settings))


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


PASSWORD = "correct-horse-1"


def _account(client: TestClient) -> dict:
    response = client.post(
        "/v1/auth/local/register",
        json={"login": f"u{uuid4().hex[:12]}", "password": PASSWORD},
        headers=_key(),
    )
    assert response.status_code == 200
    return response.json()


def test_register_enqueues_onboarding_started(client: TestClient):
    body = _account(client)
    settings = load_settings()
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        row = session.scalar(
            select(OutboxEvent)
            .where(OutboxEvent.event_name == "onboarding_started")
            .order_by(OutboxEvent.occurred_at.desc())
        )
        assert row is not None
        assert body["account_id"] in str(row.payload)
        assert "correct-horse" not in str(row.payload)
        assert "session_token" not in str(row.payload)


def test_consent_append_only_and_withdraw_queues_job(client: TestClient):
    acc = _account(client)
    auth = {"Authorization": f"Bearer {acc['session_token']}"}
    granted = client.post(
        "/v1/consents",
        json={
            "purpose": "ai_matching",
            "policy_version": PRIVACY_POLICY_VERSION,
            "decision": "granted",
        },
        headers={**auth, **_key()},
    )
    assert granted.status_code == 200
    assert granted.json()["allow_ai_matching"] is True
    withdrawn = client.post(
        "/v1/consents",
        json={
            "purpose": "ai_matching",
            "policy_version": PRIVACY_POLICY_VERSION,
            "decision": "withdrawn",
        },
        headers={**auth, **_key()},
    )
    assert withdrawn.status_code == 200
    body = withdrawn.json()
    assert body["allow_ai_matching"] is False
    assert body["discoverable"] is False
    settings = load_settings()
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        consents = list(
            session.scalars(
                select(Consent).where(Consent.account_id == acc["account_id"])
            )
        )
        assert len(consents) >= 2
        job = session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.dedup_key
                == f"invalidate_derived_matching:{acc['account_id']}"
            )
        )
        assert job is not None
        assert job.job_type == "invalidate_derived_matching"


def test_privacy_version_conflict(client: TestClient):
    acc = _account(client)
    auth = {"Authorization": f"Bearer {acc['session_token']}"}
    stale = client.patch(
        "/v1/privacy",
        json={"expected_version": 99, "show_distance": True},
        headers=auth,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"


def test_unknown_fields_rejected(client: TestClient):
    acc = _account(client)
    auth = {"Authorization": f"Bearer {acc['session_token']}"}
    response = client.post(
        "/v1/consents",
        json={
            "purpose": "ai_matching",
            "policy_version": PRIVACY_POLICY_VERSION,
            "decision": "granted",
            "account_id": acc["account_id"],
        },
        headers={**auth, **_key()},
    )
    assert response.status_code == 422
