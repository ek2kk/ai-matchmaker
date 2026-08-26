from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.app import create_app
from ai_dating.auth.crypto import hash_token
from ai_dating.auth.models import AuthSession
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine


@pytest.fixture
def client():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return TestClient(create_app(settings))


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def _login() -> str:
    return f"u{uuid4().hex[:12]}"


PASSWORD = "correct-horse-1"


@pytest.mark.integration
def test_register_creates_account_and_session(client: TestClient):
    login = _login()
    response = client.post(
        "/v1/auth/local/register",
        json={"login": login, "password": PASSWORD},
        headers=_key(),
    )
    assert response.status_code == 200
    body = response.json()
    assert "account_id" in body
    assert body["session_token"]
    assert PASSWORD not in response.text
    assert "argon2" not in response.text.lower()
    assert "$argon2" not in response.text


@pytest.mark.integration
def test_duplicate_login_conflict(client: TestClient):
    login = _login()
    client.post(
        "/v1/auth/local/register",
        json={"login": login, "password": PASSWORD},
        headers=_key(),
    )
    again = client.post(
        "/v1/auth/local/register",
        json={"login": login, "password": PASSWORD},
        headers=_key(),
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "login_unavailable"


@pytest.mark.integration
def test_register_idempotent_same_key(client: TestClient):
    login = _login()
    headers = _key()
    payload = {"login": login, "password": PASSWORD}
    first = client.post("/v1/auth/local/register", json=payload, headers=headers)
    second = client.post("/v1/auth/local/register", json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["account_id"] == second.json()["account_id"]


@pytest.mark.integration
def test_unknown_and_bad_password_match(client: TestClient):
    login = _login()
    client.post(
        "/v1/auth/local/register",
        json={"login": login, "password": PASSWORD},
        headers=_key(),
    )
    unknown = client.post(
        "/v1/auth/local/sessions",
        json={"login": "nouser999", "password": PASSWORD},
        headers=_key(),
    )
    bad = client.post(
        "/v1/auth/local/sessions",
        json={"login": login, "password": "wrong-password-1"},
        headers=_key(),
    )
    assert unknown.status_code == 401
    assert bad.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    assert bad.json()["error"]["code"] == "invalid_credentials"
    assert unknown.json()["error"]["message"] == bad.json()["error"]["message"]
    assert PASSWORD not in unknown.text


@pytest.mark.integration
def test_login_logout_and_reuse(client: TestClient):
    login = _login()
    registered = client.post(
        "/v1/auth/local/register",
        json={"login": login, "password": PASSWORD},
        headers=_key(),
    )
    token = registered.json()["session_token"]
    auth = {"Authorization": f"Bearer {token}"}
    mine = client.get("/v1/privacy", headers=auth)
    assert mine.status_code == 200
    logged_out = client.delete(
        "/v1/auth/sessions/current",
        headers={**auth, **_key()},
    )
    assert logged_out.status_code == 204
    after = client.get("/v1/privacy", headers=auth)
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "unauthenticated"


@pytest.mark.integration
def test_expired_session_is_unauthenticated(client: TestClient):
    registered = client.post(
        "/v1/auth/local/register",
        json={"login": _login(), "password": PASSWORD},
        headers=_key(),
    )
    token = registered.json()["session_token"]
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        row = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        )
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    expired = client.get("/v1/privacy", headers={"Authorization": f"Bearer {token}"})
    assert expired.status_code == 401


@pytest.mark.integration
def test_cross_account_privacy_is_404(client: TestClient):
    a = client.post(
        "/v1/auth/local/register",
        json={"login": _login(), "password": PASSWORD},
        headers=_key(),
    ).json()
    b = client.post(
        "/v1/auth/local/register",
        json={"login": _login(), "password": PASSWORD},
        headers=_key(),
    ).json()
    stolen = client.get(
        f"/v1/privacy?account_id={a['account_id']}",
        headers={"Authorization": f"Bearer {b['session_token']}"},
    )
    assert stolen.status_code == 404
    assert stolen.json()["error"]["code"] == "not_found"
    own = client.get(
        "/v1/privacy",
        headers={"Authorization": f"Bearer {b['session_token']}"},
    )
    assert own.status_code == 200
