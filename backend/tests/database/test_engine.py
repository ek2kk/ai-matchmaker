from pathlib import Path

import pytest
from sqlalchemy.engine.url import make_url

from ai_dating.config import Settings
from ai_dating.database.engine import as_async_url, as_sync_url, create_runtime_engine


def test_import_does_not_create_engine():
    import ai_dating.database.engine as engine_mod

    assert getattr(engine_mod, "engine", None) is None
    assert getattr(engine_mod, "async_engine", None) is None


def test_as_async_url_uses_psycopg():
    url = as_async_url("postgresql://u:p@localhost:5432/db")
    assert make_url(url).drivername == "postgresql+psycopg_async"


def test_as_sync_url_uses_psycopg():
    url = as_sync_url("postgresql://u:p@localhost:5432/db")
    assert make_url(url).drivername == "postgresql+psycopg"


def test_create_runtime_engine_requires_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_runtime_engine(Settings(_env_file=None))


def test_alembic_env_does_not_read_os_environ():
    text = Path("alembic/env.py").read_text()
    assert "os.getenv" not in text
    assert "os.environ" not in text
