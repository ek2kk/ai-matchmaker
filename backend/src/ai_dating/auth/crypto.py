from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from ai_dating.accounts.models import LOGIN_RE
from ai_dating.errors import AppError

_HASHER = PasswordHasher()
_DUMMY: str | None = None


def normalize_login(raw: str) -> str:
    login = raw.strip().lower()
    if not login or not LOGIN_RE.fullmatch(login):
        raise AppError(422, "validation_error", "Invalid request.")
    return login


def validate_password(password: str) -> None:
    if not password:
        raise AppError(422, "validation_error", "Invalid request.")


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def _dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = _HASHER.hash("not-a-user-" + "x" * 12)
    return _DUMMY


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def verify_unknown(password: str) -> None:
    verify_password(_dummy_hash(), password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def request_fingerprint(*parts: str) -> str:
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()
