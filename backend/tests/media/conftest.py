import pytest
from fastapi.testclient import TestClient

from ai_dating.app import create_app
from ai_dating.config import load_settings


@pytest.fixture
def client():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return TestClient(create_app(settings))
