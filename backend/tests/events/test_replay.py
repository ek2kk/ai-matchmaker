from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_dating.events.audit import SecurityAuditLog
from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.fake_sink import FakeSink
from ai_dating.events.models import OutboxEvent
from ai_dating.events.relay import run_once
from ai_dating.events.replay import replay_events
from tests.events.contracts.test_schemas import VALID


def test_replay_dry_run_does_not_write_audit(engine):
    event_id = uuid4()
    with Session(engine) as session:
        enqueue_event(session, dict(VALID["impression"]), event_id=event_id)
        session.commit()
        run_once(session, FakeSink(), owner="r1")
        before = session.scalar(select(func.count()).select_from(SecurityAuditLog))
        count = replay_events(
            session,
            [event_id],
            owner="ek",
            reason="test",
            dry_run=True,
        )
        assert count == 1
        after = session.scalar(select(func.count()).select_from(SecurityAuditLog))
        assert after == before
        assert session.get(OutboxEvent, event_id).delivered_at is not None


def test_replay_clears_delivered_and_audits(engine):
    event_id = uuid4()
    with Session(engine) as session:
        enqueue_event(session, dict(VALID["impression"]), event_id=event_id)
        session.commit()
        run_once(session, FakeSink(), owner="r1")
        replay_events(session, [event_id], owner="ek", reason="reprocess")
        row = session.get(OutboxEvent, event_id)
        assert row.delivered_at is None
        assert row.event_id == event_id
        audit = session.scalars(
            select(SecurityAuditLog).where(SecurityAuditLog.resource_id == event_id)
        ).first()
        assert audit is not None
        assert audit.action == "outbox_replay"
        assert audit.metadata_json["reason"] == "reprocess"
