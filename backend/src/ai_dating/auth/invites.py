from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from ai_dating.auth.crypto import hash_token
from ai_dating.auth.models import AuthInvite
from ai_dating.config import load_settings, require_startup
from ai_dating.database.engine import create_sync_engine


def create_invite() -> str:
    settings = load_settings()
    require_startup(settings)
    if settings.app_env == "local":
        raise RuntimeError("Telegram invites require staging or production")
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with Session(create_sync_engine(settings)) as db:
        db.add(
            AuthInvite(
                invite_id=uuid4(),
                token_hash=hash_token(token),
                expires_at=now + timedelta(days=7),
                used_at=None,
                admitted_account_id=None,
                created_at=now,
            )
        )
        db.commit()
    return token


def main() -> None:
    print(create_invite())
