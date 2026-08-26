from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.auth.models import AuthSession
from ai_dating.auth.sessions import load_actor
from ai_dating.errors import AppError


def get_db(request: Request) -> Generator[Session]:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise AppError(503, "dependency_unavailable", "Service is not ready.")
    db = Session(engine)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require_idempotency_key(request: Request) -> str:
    raw = request.headers.get("idempotency-key", "").strip()
    try:
        return str(UUID(raw))
    except ValueError:
        raise AppError(422, "validation_error", "Invalid request.") from None


def get_actor(request: Request, db: Session) -> tuple[Account, AuthSession]:
    return load_actor(db, request.headers.get("authorization"))
