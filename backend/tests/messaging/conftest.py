import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_dating.app import create_app
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine

pytestmark = [pytest.mark.postgres]


@pytest.fixture
def db():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        yield session
        session.commit()


@pytest.fixture
def client():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return TestClient(create_app(settings))
