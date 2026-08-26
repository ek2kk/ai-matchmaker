from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.fake_sink import FakeSink
from ai_dating.events.models import OutboxEvent
from ai_dating.events.relay import run_once
from ai_dating.events.retry import backoff_delay
from tests.events.contracts.test_schemas import VALID


def test_backoff_grows_and_caps():
    first = backoff_delay(1).total_seconds()
    later = backoff_delay(12).total_seconds()
    assert 10 <= first <= 12
    assert later <= 15 * 60 * 1.1


def test_poison_row_is_isolated(engine):
    good_id = uuid4()
    bad_id = uuid4()
    sink = FakeSink()
    sink.reject_ids.add(str(bad_id))
    with Session(engine) as session:
        enqueue_event(session, dict(VALID["impression"]), event_id=good_id)
        enqueue_event(session, dict(VALID["block"]), event_id=bad_id)
        session.commit()
        run_once(session, sink, owner="r1", limit=50)
        good = session.get(OutboxEvent, good_id)
        bad = session.get(OutboxEvent, bad_id)
        assert good.delivered_at is not None
        assert bad.delivered_at is None
        assert bad.last_error_code == "sink_rejected"
        assert str(bad_id) not in [row["event_id"] for row in sink.rows]


def test_delivered_row_is_not_deleted(engine):
    event_id = uuid4()
    with Session(engine) as session:
        enqueue_event(session, dict(VALID["impression"]), event_id=event_id)
        session.commit()
        run_once(session, FakeSink(), owner="r1")
        assert session.get(OutboxEvent, event_id) is not None
