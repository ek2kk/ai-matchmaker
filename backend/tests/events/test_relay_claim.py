from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ai_dating.events.enqueue import enqueue_event
from ai_dating.events.models import OutboxEvent
from ai_dating.events.relay import claim_batch
from tests.events.contracts.test_schemas import VALID


def _enqueue(session: Session) -> UUID:
    payload = dict(VALID["impression"])
    event_id = uuid4()
    enqueue_event(session, payload, event_id=event_id)
    session.commit()
    return event_id


def test_claim_skips_active_lease(engine):
    with Session(engine) as session:
        event_id = _enqueue(session)
        first = claim_batch(session, owner="a", limit=50, lease_seconds=60)
        assert event_id in {row.event_id for row in first}
        second = claim_batch(session, owner="b", limit=50, lease_seconds=60)
        assert event_id not in {row.event_id for row in second}


def test_expired_lease_is_reclaimed(engine):
    with Session(engine) as session:
        event_id = _enqueue(session)
        row = session.get(OutboxEvent, event_id)
        row.lease_owner = "a"
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        claimed = claim_batch(session, owner="b", limit=50, lease_seconds=60)
        assert event_id in {item.event_id for item in claimed}
