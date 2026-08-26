from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_dating.events.audit import SecurityAuditLog
from ai_dating.events.models import OutboxEvent

log = structlog.get_logger("ai_dating.replay")


def replay_events(
    session: Session,
    event_ids: list[UUID],
    *,
    owner: str,
    reason: str,
    dry_run: bool = False,
) -> int:
    rows = list(
        session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_id.in_(event_ids))
        ).all()
    )
    count = len(rows)
    log.info(
        "outbox_replay",
        event_id_count=count,
        dry_run=dry_run,
        error_code=None,
    )
    if dry_run:
        return count
    now = datetime.now(UTC)
    session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.event_id.in_(event_ids))
        .values(
            delivered_at=None,
            lease_owner=None,
            lease_until=None,
            available_at=now,
        )
    )
    session.add(
        SecurityAuditLog(
            audit_id=uuid4(),
            action="outbox_replay",
            actor_type="owner",
            actor_id=None,
            subject_account_id=None,
            resource_type="outbox_events",
            resource_id=event_ids[0] if event_ids else None,
            request_id="",
            metadata_json={
                "owner": owner,
                "reason": reason,
                "event_ids": [str(i) for i in event_ids],
            },
            occurred_at=now,
        )
    )
    session.commit()
    return count
