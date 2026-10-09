from fastapi.testclient import TestClient

from ai_dating.app import create_app
from ai_dating.config import Settings


def test_readyz_local_without_db(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_503_when_production_incomplete():
    settings = Settings(
        _env_file=None,
        app_env="production",
        release_id="rel-1",
        database_url=None,
        database_direct_url=None,
        dslab_api_key="test",
        telegram_bot_token="test",
        media_auto_approve=False,
        message_auto_approve=False,
    )
    response = TestClient(create_app(settings)).get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "dependency_unavailable"
    assert body["error"]["request_id"]
    assert "postgres" not in response.text.lower()
    assert "postgresql" not in response.text.lower()
