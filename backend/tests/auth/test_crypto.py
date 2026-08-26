import pytest

from ai_dating.auth.crypto import (
    hash_password,
    hash_token,
    normalize_login,
    validate_password,
)
from ai_dating.errors import AppError


def test_normalize_login_lowercases():
    assert normalize_login("  Alice.1 ") == "alice.1"


def test_normalize_login_accepts_short():
    assert normalize_login("ab") == "ab"


def test_normalize_login_rejects_empty():
    with pytest.raises(AppError) as exc:
        normalize_login("  ")
    assert exc.value.status == 422


def test_normalize_login_rejects_symbols():
    with pytest.raises(AppError):
        normalize_login("alice@x")


def test_password_rejects_empty():
    with pytest.raises(AppError) as exc:
        validate_password("")
    assert exc.value.status == 422


def test_password_accepts_short():
    validate_password("short")


def test_hash_is_argon2_and_not_plaintext():
    password = "correct-horse-1"
    hashed = hash_password(password)
    assert hashed.startswith("$argon2")
    assert password not in hashed


def test_token_hash_is_sha256_hex():
    digest = hash_token("opaque-token")
    assert len(digest) == 64
    assert "opaque-token" not in digest
