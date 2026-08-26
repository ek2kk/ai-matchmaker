from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_dating.auth.models import IdempotencyKey
from ai_dating.errors import AppError

_TTL = timedelta(hours=24)


def claim_idempotency(
    session: Session,
    *,
    scope: str,
    key: str,
    request_hash: str,
    account_id: UUID | None = None,
) -> tuple[IdempotencyKey, bool]:
    """Return (row, replay). replay True means identical prior request."""
    now = datetime.now(UTC)
    existing = _lookup(session, scope, key, account_id)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise AppError(409, "idempotency_conflict", "Idempotency key reused.")
        return existing, True
    row = IdempotencyKey(
        idempotency_id=uuid4(),
        account_id=account_id,
        scope=scope,
        key=key,
        request_hash=request_hash,
        response_status=None,
        response_body=None,
        resource_type=None,
        resource_id=None,
        created_at=now,
        expires_at=now + _TTL,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = _lookup(session, scope, key, account_id)
        if existing is None or existing.request_hash != request_hash:
            raise AppError(409, "idempotency_conflict", "Idempotency key reused.")
        return existing, True
    return row, False


def _lookup(
    session: Session, scope: str, key: str, account_id: UUID | None
) -> IdempotencyKey | None:
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.scope == scope, IdempotencyKey.key == key
    )
    if account_id is None:
        stmt = stmt.where(IdempotencyKey.account_id.is_(None))
    else:
        stmt = stmt.where(IdempotencyKey.account_id == account_id)
    return session.scalar(stmt)
