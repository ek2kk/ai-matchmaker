from __future__ import annotations

import hmac
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_dating.accounts.service import admit_telegram
from ai_dating.app import create_app
from ai_dating.auth.crypto import hash_token
from ai_dating.auth.models import AuthIdentity, AuthInvite
from ai_dating.config import Settings, load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.errors import AppError

TOKEN = "123456:telegram-test-token"


@pytest.fixture
def engine():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return create_sync_engine(settings)


@pytest.fixture
def client() -> TestClient:
    base = load_settings()
    if not (base.database_url or base.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    settings = Settings(
        _env_file=None,
        app_env="staging",
        release_id="telegram-integration",
        database_url=base.database_url,
        database_direct_url=base.database_direct_url,
        dslab_api_key="test",
        telegram_bot_token=TOKEN,
        media_auto_approve=False,
        message_auto_approve=False,
    )
    return TestClient(create_app(settings))


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def _init_data(user_id: int, *, invite: str | None = None) -> str:
    values = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "user": f'{{"id":{user_id},"first_name":"Ada"}}',
    }
    if invite:
        values["start_param"] = invite
    secret = hmac.digest(b"WebAppData", TOKEN.encode(), "sha256")
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    values["hash"] = hmac.digest(secret, check.encode(), "sha256").hex()
    return urlencode(values)


def _invite(engine) -> str:
    token = uuid4().hex
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.add(
            AuthInvite(
                invite_id=uuid4(),
                token_hash=hash_token(token),
                expires_at=now + timedelta(days=1),
                used_at=None,
                admitted_account_id=None,
                created_at=now,
            )
        )
        db.commit()
    return token


@pytest.mark.postgres
def test_telegram_admission_consumes_invite_and_existing_login_needs_none(
    client: TestClient, engine
):
    invite = _invite(engine)
    user_id = int(uuid4().int % 1_000_000_000) + 1
    created = client.post(
        "/v1/auth/telegram/sessions",
        json={"init_data": _init_data(user_id, invite=invite)},
        headers=_key(),
    )
    assert created.status_code == 200
    again = client.post(
        "/v1/auth/telegram/sessions",
        json={"init_data": _init_data(user_id)},
        headers=_key(),
    )
    assert again.status_code == 200
    assert again.json()["account_id"] == created.json()["account_id"]
    with Session(engine) as db:
        row = db.scalar(
            select(AuthInvite).where(AuthInvite.token_hash == hash_token(invite))
        )
        assert row is not None and row.used_at is not None


@pytest.mark.postgres
def test_telegram_admission_rejects_missing_or_reused_invite(
    client: TestClient, engine
):
    invite = _invite(engine)
    missing = client.post(
        "/v1/auth/telegram/sessions",
        json={"init_data": _init_data(int(uuid4().int % 1_000_000_000) + 1)},
        headers=_key(),
    )
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "invite_required"
    for _ in range(2):
        response = client.post(
            "/v1/auth/telegram/sessions",
            json={
                "init_data": _init_data(
                    int(uuid4().int % 1_000_000_000) + 1, invite=invite
                )
            },
            headers=_key(),
        )
        if _ == 0:
            assert response.status_code == 200
        else:
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "invite_invalid"


@pytest.mark.postgres
def test_concurrent_telegram_registration_creates_one_identity(engine):
    user_id = str(int(uuid4().int % 1_000_000_000) + 1)
    invites = [_invite(engine), _invite(engine)]
    barrier = Barrier(2)

    def admit(token: str):
        with Session(engine) as db:
            barrier.wait()
            result = admit_telegram(
                db,
                user_id=user_id,
                invite_token_hash=hash_token(token),
                admission_open=True,
                cohort_limit=100,
                ttl_seconds=86400,
            )
            db.commit()
            return result[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        accounts = list(executor.map(admit, invites))
    assert accounts[0] == accounts[1]
    with Session(engine) as db:
        identities = list(
            db.scalars(
                select(AuthIdentity).where(
                    AuthIdentity.provider == "telegram",
                    AuthIdentity.provider_subject == user_id,
                )
            )
        )
    assert len(identities) == 1


@pytest.mark.postgres
def test_telegram_admission_respects_cohort_limit(engine):
    with Session(engine) as db:
        admitted = db.scalar(
            select(func.count())
            .select_from(AuthIdentity)
            .where(AuthIdentity.provider == "telegram")
        )
    first_invite, second_invite = _invite(engine), _invite(engine)
    with Session(engine) as db:
        admit_telegram(
            db,
            user_id=str(int(uuid4().int % 1_000_000_000) + 1),
            invite_token_hash=hash_token(first_invite),
            admission_open=True,
            cohort_limit=admitted + 1,
            ttl_seconds=86400,
        )
        db.commit()
    with Session(engine) as db, pytest.raises(AppError, match="Admission is closed"):
        admit_telegram(
            db,
            user_id=str(int(uuid4().int % 1_000_000_000) + 1),
            invite_token_hash=hash_token(second_invite),
            admission_open=True,
            cohort_limit=admitted + 1,
            ttl_seconds=86400,
        )


@pytest.mark.postgres
def test_telegram_session_cannot_read_another_accounts_privacy(
    client: TestClient, engine
):
    sessions = []
    for _ in range(2):
        invite = _invite(engine)
        response = client.post(
            "/v1/auth/telegram/sessions",
            json={
                "init_data": _init_data(
                    int(uuid4().int % 1_000_000_000) + 1, invite=invite
                )
            },
            headers=_key(),
        )
        assert response.status_code == 200
        sessions.append(response.json())
    forbidden = client.get(
        f"/v1/privacy?account_id={sessions[0]['account_id']}",
        headers={"Authorization": f"Bearer {sessions[1]['session_token']}"},
    )
    assert forbidden.status_code == 404
