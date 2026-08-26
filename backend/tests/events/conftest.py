from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent


@pytest.fixture
def engine():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    created = create_sync_engine(settings)
    with Session(created) as session:
        session.execute(delete(OutboxEvent).where(OutboxEvent.delivered_at.is_(None)))
        session.commit()
    return created
