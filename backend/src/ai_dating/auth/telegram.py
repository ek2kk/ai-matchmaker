from __future__ import annotations

import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from ai_dating.errors import AppError

_MAX_INIT_DATA_BYTES = 8192


@dataclass(frozen=True)
class TelegramLaunch:
    user_id: str
    start_param: str | None


def verify_init_data(
    init_data: str, *, bot_token: str, max_age_seconds: int, now: int | None = None
) -> TelegramLaunch:
    if not init_data or len(init_data.encode()) > _MAX_INIT_DATA_BYTES:
        _invalid()
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        _invalid()
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            _invalid()
        values[key] = value
    received_hash = values.pop("hash", None)
    if not received_hash or not values.get("auth_date") or not values.get("user"):
        _invalid()
    secret = hmac.digest(b"WebAppData", bot_token.encode(), "sha256")
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    expected_hash = hmac.digest(secret, check_string.encode(), "sha256").hex()
    if not hmac.compare_digest(expected_hash, received_hash):
        _invalid()
    try:
        auth_date = int(values["auth_date"])
        user = json.loads(values["user"])
        user_id = user["id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        _invalid()
    if type(user_id) is not int or user_id <= 0:
        _invalid()
    current = int(time.time()) if now is None else now
    if auth_date > current + 30 or current - auth_date > max_age_seconds:
        _invalid()
    return TelegramLaunch(user_id=str(user_id), start_param=values.get("start_param"))


def _invalid() -> None:
    raise AppError(401, "invalid_telegram_launch", "Invalid Telegram launch data.")
