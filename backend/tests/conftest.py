import pytest
from fastapi.testclient import TestClient

from ai_dating.app import create_app
from ai_dating.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
