from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_dating.app import create_app
from ai_dating.config import Settings
from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.fake_sink import FakeSink
from ai_dating.events.relay import run_once
from tests.events.contracts.test_schemas import VALID


def test_readyz_local_without_clickhouse(client):
    response = client.get("/readyz")
    assert response.status_code == 200


def test_readyz_503_when_clickhouse_configured_and_down():
    settings = Settings(
        clickhouse_url="http://127.0.0.1:1",
        clickhouse_timeout_seconds=0.2,
    )
    response = TestClient(create_app(settings)).get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"


def test_relay_metrics_have_no_payload(engine):
    sink = FakeSink()
    with Session(engine) as session:
        enqueue_event(session, dict(VALID["impression"]), event_id=uuid4())
        session.commit()
        metrics = run_once(session, sink, owner="r1")
    assert "payload" not in metrics.__dict__
    assert metrics.delivered >= 0
