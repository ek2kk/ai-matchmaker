from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.auth.crypto import hash_token, new_session_token
from ai_dating.auth.models import AuthSession
from ai_dating.errors import AppError


def issue_session(
    session: Session, account_id: UUID, ttl_seconds: int
) -> tuple[str, AuthSession]:
    now = datetime.now(UTC)
    token = new_session_token()
    row = AuthSession(
        session_id=uuid4(),
        account_id=account_id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(seconds=ttl_seconds),
        revoked_at=None,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return token, row


def revoke_session(session: Session, session_id: UUID) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.session_id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def revoke_all_sessions(session: Session, account_id: UUID) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def load_actor(session: Session, bearer: str | None) -> tuple[Account, AuthSession]:
    if not bearer or not bearer.lower().startswith("bearer "):
        raise AppError(401, "unauthenticated", "Authentication required.")
    token = bearer.split(" ", 1)[1].strip()
    if not token:
        raise AppError(401, "unauthenticated", "Authentication required.")
    now = datetime.now(UTC)
    row = session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if row is None:
        raise AppError(401, "unauthenticated", "Authentication required.")
    account = session.get(Account, row.account_id)
    if account is None or account.deleted_at is not None:
        raise AppError(401, "unauthenticated", "Authentication required.")
    return account, row
