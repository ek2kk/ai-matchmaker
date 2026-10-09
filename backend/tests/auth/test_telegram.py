from __future__ import annotations

import hmac
from urllib.parse import urlencode

import pytest

from ai_dating.auth.telegram import verify_init_data
from ai_dating.errors import AppError

TOKEN = "123456:telegram-test-token"
NOW = 1_700_000_000


def _init_data(**values: str) -> str:
    secret = hmac.digest(b"WebAppData", TOKEN.encode(), "sha256")
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    values["hash"] = hmac.digest(secret, check_string.encode(), "sha256").hex()
    return urlencode(values)


def test_verify_init_data_accepts_official_hmac_shape():
    launch = verify_init_data(
        _init_data(
            auth_date=str(NOW),
            start_param="invite-token",
            user='{"id":123456789,"first_name":"Ada"}',
        ),
        bot_token=TOKEN,
        max_age_seconds=300,
        now=NOW,
    )
    assert launch.user_id == "123456789"
    assert launch.start_param == "invite-token"


@pytest.mark.parametrize(
    "init_data",
    [
        _init_data(auth_date=str(NOW), user='{"id":1}') + "&auth_date=1",
        _init_data(auth_date=str(NOW), user='{"id":1}').replace("auth_date", "x", 1),
        _init_data(auth_date=str(NOW), user='{"id":1}').replace("%7D", "%7D0", 1),
    ],
)
def test_verify_init_data_rejects_tampering_and_duplicate_fields(init_data: str):
    with pytest.raises(AppError, match="Invalid Telegram launch data"):
        verify_init_data(init_data, bot_token=TOKEN, max_age_seconds=300, now=NOW)


@pytest.mark.parametrize("auth_date", [NOW - 301, NOW + 31])
def test_verify_init_data_rejects_stale_or_future_launch(auth_date: int):
    with pytest.raises(AppError, match="Invalid Telegram launch data"):
        verify_init_data(
            _init_data(auth_date=str(auth_date), user='{"id":1}'),
            bot_token=TOKEN,
            max_age_seconds=300,
            now=NOW,
        )
