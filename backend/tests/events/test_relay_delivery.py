from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.fake_sink import FakeSink
from ai_dating.events.models import OutboxEvent
from ai_dating.events.relay import run_once
from tests.events.contracts.test_schemas import VALID


def test_delivery_marks_delivered_and_keeps_row(engine):
    payload = dict(VALID["impression"])
    event_id = uuid4()
    sink = FakeSink()
    with Session(engine) as session:
        enqueue_event(session, payload, event_id=event_id)
        session.commit()
        metrics = run_once(session, sink, owner="r1")
    assert metrics.delivered == 1
    assert sink.rows[0]["event_id"] == str(event_id)
    with Session(engine) as session:
        row = session.get(OutboxEvent, event_id)
        assert row is not None
        assert row.delivered_at is not None


def test_crash_after_sink_replays_same_event_id(engine):
    payload = dict(VALID["onboarding_started"])
    event_id = uuid4()
    sink = FakeSink()

    def crash(_payloads: list[dict]) -> None:
        raise RuntimeError("crash after sink")

    sink.before_return = crash
    with Session(engine) as session:
        enqueue_event(session, payload, event_id=event_id)
        session.commit()
        try:
            run_once(session, sink, owner="r1", lease_seconds=60)
        except RuntimeError:
            pass
        row = session.get(OutboxEvent, event_id)
        assert row is not None
        assert row.delivered_at is None
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        sink.before_return = None
        run_once(session, sink, owner="r2", lease_seconds=60)
    ids = [item["event_id"] for item in sink.rows]
    assert ids.count(str(event_id)) == 2
    with Session(engine) as session:
        assert session.get(OutboxEvent, event_id).delivered_at is not None
