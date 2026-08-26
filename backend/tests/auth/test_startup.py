import pytest
from fastapi.testclient import TestClient

from ai_dating.app import create_app
from ai_dating.config import Settings, require_startup


def test_local_non_loopback_refuses_startup():
    settings = Settings(_env_file=None, bind_host="0.0.0.0")
    with pytest.raises(RuntimeError, match="loopback"):
        require_startup(settings)


def test_local_loopback_starts_without_db():
    require_startup(Settings(_env_file=None, bind_host="127.0.0.1"))


def test_production_has_no_local_auth_routes():
    settings = Settings(
        _env_file=None,
        app_env="production",
        release_id="rel-1",
        database_url="postgresql://u@127.0.0.1:5432/db",
        database_direct_url="postgresql://u@127.0.0.1:5432/db",
        media_auto_approve=False,
        message_auto_approve=False,
    )
    client = TestClient(create_app(settings))
    response = client.post(
        "/v1/auth/local/register",
        json={"login": "abc", "password": "x" * 12},
    )
    assert response.status_code == 404
