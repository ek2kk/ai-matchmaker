from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.events.models import OutboxEvent
from ai_dating.events.validate import EventValidationError, validate_event

log = structlog.get_logger("ai_dating.events")


def enqueue_event(
    session: Session, payload: dict, *, event_id: UUID | None = None
) -> UUID:
    body = dict(payload)
    eid = event_id or uuid4()
    body["event_id"] = str(eid)
    occurred = datetime.now(UTC)
    body["occurred_at"] = occurred.isoformat().replace("+00:00", "Z")
    try:
        validate_event(body)
    except EventValidationError:
        log.info(
            "outbox_rejected",
            event_id=str(eid),
            event_name=body.get("event_name"),
            schema_version=body.get("schema_version"),
            error_code="schema_invalid",
        )
        raise
    subject = body.get("subject_account_id")
    actor = body.get("actor_account_id")
    aggregate_id = UUID(subject or actor or str(eid))
    stmt = (
        insert(OutboxEvent)
        .values(
            event_id=eid,
            event_name=body["event_name"],
            schema_version=body["schema_version"],
            aggregate_type=body["owner"],
            aggregate_id=aggregate_id,
            payload=body,
            occurred_at=occurred,
            available_at=occurred,
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    session.execute(stmt)
    log.info(
        "outbox_enqueued",
        event_id=str(eid),
        event_name=body["event_name"],
        schema_version=body["schema_version"],
    )
    return eid
