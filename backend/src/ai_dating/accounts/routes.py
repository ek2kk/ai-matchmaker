from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ai_dating.accounts.service import authenticate, create_account, mint_session
from ai_dating.auth.crypto import request_fingerprint
from ai_dating.auth.sessions import revoke_session
from ai_dating.config import Settings
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency

router = APIRouter()


class CredentialsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login: str
    password: str


def _ttl(request: Request) -> int:
    settings: Settings = request.app.state.settings
    return settings.session_ttl_seconds


def _session_body(account_id: UUID, token: str, expires_at: datetime) -> dict:
    return {
        "account_id": str(account_id),
        "session_token": token,
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.post("/v1/auth/local/register")
def register(
    body: CredentialsIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    digest = request_fingerprint(body.login.strip().lower(), body.password)
    row, replay = claim_idempotency(
        db, scope="auth.local.register", key=key, request_hash=digest
    )
    ttl = _ttl(request)
    if replay and row.resource_id is not None:
        account_id, token, expires_at = mint_session(db, row.resource_id, ttl)
        return _session_body(account_id, token, expires_at)
    account_id, token, expires_at = create_account(db, body.login, body.password, ttl)
    row.resource_type = "accounts"
    row.resource_id = account_id
    row.response_status = 200
    row.response_body = {"account_id": str(account_id)}
    return _session_body(account_id, token, expires_at)


@router.post("/v1/auth/local/sessions")
def login(
    body: CredentialsIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    digest = request_fingerprint(body.login.strip().lower(), body.password)
    row, replay = claim_idempotency(
        db, scope="auth.local.sessions", key=key, request_hash=digest
    )
    ttl = _ttl(request)
    if replay and row.resource_id is not None:
        account_id, token, expires_at = mint_session(db, row.resource_id, ttl)
        return _session_body(account_id, token, expires_at)
    account_id, token, expires_at = authenticate(db, body.login, body.password, ttl)
    row.resource_type = "accounts"
    row.resource_id = account_id
    row.response_status = 200
    row.response_body = {"account_id": str(account_id)}
    return _session_body(account_id, token, expires_at)


@router.delete("/v1/auth/sessions/current")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, sess = get_actor(request, db)
    row, replay = claim_idempotency(
        db,
        scope="auth.sessions.current",
        key=key,
        request_hash="logout",
        account_id=account.account_id,
    )
    if not replay:
        revoke_session(db, sess.session_id)
        row.resource_type = "auth_sessions"
        row.resource_id = sess.session_id
        row.response_status = 204
        row.response_body = {}
    return Response(status_code=204)
