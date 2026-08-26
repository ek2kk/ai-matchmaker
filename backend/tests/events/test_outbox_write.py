from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.models import OutboxEvent
from tests.events.contracts.test_schemas import VALID


def test_commit_writes_domain_and_outbox(engine):
    payload = dict(VALID["impression"])
    event_id = uuid4()
    probe_id = uuid4()
    with engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn)
        session.execute(text("CREATE TEMP TABLE domain_probe (id uuid PRIMARY KEY)"))
        session.execute(text("INSERT INTO domain_probe VALUES (:id)"), {"id": probe_id})
        enqueue_event(session, payload, event_id=event_id)
        trans.commit()
    with Session(engine) as session:
        assert session.get(OutboxEvent, event_id) is not None


def test_rollback_drops_domain_and_outbox(engine):
    payload = dict(VALID["impression"])
    event_id = uuid4()
    with engine.connect() as conn:
        trans = conn.begin()
        session = Session(bind=conn)
        session.execute(text("CREATE TEMP TABLE domain_probe (id uuid PRIMARY KEY)"))
        session.execute(text("INSERT INTO domain_probe VALUES (:id)"), {"id": uuid4()})
        enqueue_event(session, payload, event_id=event_id)
        trans.rollback()
    with Session(engine) as session:
        assert session.get(OutboxEvent, event_id) is None


def test_same_event_id_does_not_duplicate(engine):
    payload = dict(VALID["onboarding_started"])
    event_id = uuid4()
    with Session(engine) as session:
        enqueue_event(session, payload, event_id=event_id)
        enqueue_event(session, payload, event_id=event_id)
        session.commit()
        count = session.query(OutboxEvent).filter_by(event_id=event_id).count()
        assert count == 1
