import pytest
from pydantic import ValidationError

from ai_dating.config import Settings, load_settings, require_startup


def test_local_defaults():
    settings = Settings(_env_file=None)
    assert settings.app_env == "local"
    assert settings.database_url is None
    assert settings.bind_host == "127.0.0.1"
    assert "http://localhost:5173" in settings.cors_origins


def test_rejects_sqlite():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(database_url="sqlite:///./app.db")


def test_rejects_cors_wildcard():
    with pytest.raises(ValidationError, match="allowlist"):
        Settings(cors_origins=("*",))


def test_cors_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_DIRECT_URL", raising=False)
    settings = load_settings()
    assert settings.cors_origins == ("http://localhost:5173",)


def test_require_startup_production_missing_db():
    settings = Settings(
        _env_file=None,
        app_env="production",
        release_id="rel-1",
        database_url=None,
        database_direct_url=None,
        media_auto_approve=False,
        message_auto_approve=False,
    )
    with pytest.raises(RuntimeError, match="required configuration"):
        require_startup(settings)


def test_require_startup_local_without_db():
    require_startup(Settings(_env_file=None))


def test_rerank_enabled_requires_passing_manifest():
    with pytest.raises(ValidationError, match="passing evaluation"):
        Settings(_env_file=None, rerank_enabled=True)
