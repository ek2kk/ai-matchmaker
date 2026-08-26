from __future__ import annotations

import base64
import hashlib
import hmac
import time

from ai_dating.errors import AppError


def _b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _unb64(raw: str) -> str:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad).decode()


def sign_token(secret: str, kind: str, value: str, expires_at: int) -> str:
    packed = _b64(value)
    payload = f"{kind}.{expires_at}.{packed}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{digest}"


def read_token(secret: str, token: str, kind: str) -> str:
    try:
        expected_kind, expires_s, packed, digest = token.split(".")
        expires_at = int(expires_s)
        payload = f"{expected_kind}.{expires_at}.{packed}"
        value = _unb64(packed)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError(404, "not_found", "Not found.") from exc
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if (
        expected_kind != kind
        or not hmac.compare_digest(expected, digest)
        or expires_at < int(time.time())
    ):
        raise AppError(404, "not_found", "Not found.")
    return value
