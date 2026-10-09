from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ai_dating.accounts.service import admit_telegram, mint_session
from ai_dating.auth.crypto import hash_token, request_fingerprint
from ai_dating.auth.telegram import verify_init_data
from ai_dating.config import Settings
from ai_dating.deps import get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency

router = APIRouter()


class TelegramSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    init_data: str


def _session_body(account_id: UUID, token: str, expires_at: datetime) -> dict:
    return {
        "account_id": str(account_id),
        "session_token": token,
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.post("/v1/auth/telegram/sessions")
def telegram_session(
    body: TelegramSessionIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    settings: Settings = request.app.state.settings
    launch = verify_init_data(
        body.init_data,
        bot_token=settings.telegram_bot_token or "",
        max_age_seconds=settings.telegram_init_data_ttl_seconds,
    )
    row, replay = claim_idempotency(
        db,
        scope="auth.telegram.sessions",
        key=key,
        request_hash=request_fingerprint(body.init_data),
    )
    if replay and row.resource_id is not None:
        account_id, token, expires_at = mint_session(
            db, row.resource_id, settings.session_ttl_seconds
        )
        return _session_body(account_id, token, expires_at)
    account_id, token, expires_at = admit_telegram(
        db,
        user_id=launch.user_id,
        invite_token_hash=(
            hash_token(launch.start_param) if launch.start_param else None
        ),
        admission_open=settings.telegram_admission_open,
        cohort_limit=settings.telegram_admission_cohort_limit,
        ttl_seconds=settings.session_ttl_seconds,
    )
    row.resource_type = "accounts"
    row.resource_id = account_id
    row.response_status = 200
    row.response_body = {"account_id": str(account_id)}
    return _session_body(account_id, token, expires_at)
