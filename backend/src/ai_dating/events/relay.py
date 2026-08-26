from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ai_dating.events.metrics import RelayMetrics
from ai_dating.events.models import OutboxEvent
from ai_dating.events.retry import ERROR_CODES, backoff_delay
from ai_dating.events.sink import EventSink, InsertResult

log = structlog.get_logger("ai_dating.relay")
ALERT_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class ClaimedEvent:
    event_id: UUID
    payload: dict
    attempts: int
    event_name: str
    schema_version: int
    occurred_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def claim_batch(
    session: Session,
    *,
    owner: str,
    limit: int,
    lease_seconds: int,
) -> list[ClaimedEvent]:
    now = _now()
    rows = (
        session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.delivered_at.is_(None),
                OutboxEvent.available_at <= now,
                or_(OutboxEvent.lease_until.is_(None), OutboxEvent.lease_until < now),
            )
            .order_by(OutboxEvent.available_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    until = now + timedelta(seconds=lease_seconds)
    claimed: list[ClaimedEvent] = []
    for row in rows:
        row.lease_owner = owner
        row.lease_until = until
        row.attempts += 1
        claimed.append(
            ClaimedEvent(
                event_id=row.event_id,
                payload=dict(row.payload),
                attempts=row.attempts,
                event_name=row.event_name,
                schema_version=row.schema_version,
                occurred_at=row.occurred_at,
            )
        )
    session.commit()
    return claimed


def _mark_delivered(session: Session, event_ids: list[UUID]) -> None:
    if not event_ids:
        return
    session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.event_id.in_(event_ids))
        .values(
            delivered_at=_now(),
            lease_owner=None,
            lease_until=None,
            last_error_code=None,
        )
    )
    session.commit()


def _log_fields(row: ClaimedEvent) -> dict:
    return {
        "event_id": str(row.event_id),
        "event_name": row.event_name,
        "schema_version": row.schema_version,
        "request_id": row.payload.get("request_id"),
    }


def _defer(session: Session, event_id: UUID, attempts: int, error_code: str) -> None:
    if error_code not in ERROR_CODES:
        error_code = "sink_unavailable"
    session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.event_id == event_id)
        .values(
            available_at=_now() + backoff_delay(attempts),
            lease_owner=None,
            lease_until=None,
            last_error_code=error_code,
        )
    )
    session.commit()


def _deliver_one(
    session: Session,
    sink: EventSink,
    row: ClaimedEvent,
    metrics: RelayMetrics,
) -> InsertResult:
    start = time.perf_counter()
    result = sink.insert([row.payload])
    metrics.delivery_latency_ms = round((time.perf_counter() - start) * 1000, 1)
    if result is InsertResult.SUCCESS:
        _mark_delivered(session, [row.event_id])
        metrics.delivered += 1
        log.info("outbox_delivered", **_log_fields(row))
        return result
    error_code = (
        "sink_rejected" if result is InsertResult.REJECTED else "sink_unavailable"
    )
    _defer(session, row.event_id, row.attempts, error_code)
    metrics.failed += 1
    age = _now() - row.occurred_at
    if age >= ALERT_AFTER:
        metrics.alerts.append(str(row.event_id))
        log.info("outbox_alert", error_code=error_code, **_log_fields(row))
    else:
        log.info("outbox_retry", error_code=error_code, **_log_fields(row))
    return result


def deliver_claimed(
    session: Session,
    sink: EventSink,
    rows: list[ClaimedEvent],
    metrics: RelayMetrics,
) -> None:
    if not rows:
        return
    start = time.perf_counter()
    result = sink.insert([row.payload for row in rows])
    metrics.delivery_latency_ms = round((time.perf_counter() - start) * 1000, 1)
    if result is InsertResult.SUCCESS:
        _mark_delivered(session, [row.event_id for row in rows])
        metrics.delivered += len(rows)
        for row in rows:
            log.info("outbox_delivered", **_log_fields(row))
        return
    for row in rows:
        _deliver_one(session, sink, row, metrics)


def collect_metrics(session: Session, metrics: RelayMetrics) -> None:
    now = _now()
    pending = session.scalar(
        select(func.count())
        .select_from(OutboxEvent)
        .where(OutboxEvent.delivered_at.is_(None))
    )
    oldest = session.scalar(
        select(func.min(OutboxEvent.occurred_at)).where(
            OutboxEvent.delivered_at.is_(None)
        )
    )
    expired = session.scalar(
        select(func.count())
        .select_from(OutboxEvent)
        .where(
            and_(
                OutboxEvent.delivered_at.is_(None),
                OutboxEvent.lease_until.is_not(None),
                OutboxEvent.lease_until < now,
            )
        )
    )
    metrics.pending_depth = int(pending or 0)
    metrics.lease_expiry = int(expired or 0)
    if oldest is not None:
        metrics.oldest_age_seconds = (now - oldest).total_seconds()
        metrics.lag_seconds = metrics.oldest_age_seconds
    log.info(
        "outbox_metrics",
        pending_depth=metrics.pending_depth,
        oldest_age_seconds=metrics.oldest_age_seconds,
        lease_expiry=metrics.lease_expiry,
        attempts=metrics.attempts,
        delivery_latency_ms=metrics.delivery_latency_ms,
        delivered=metrics.delivered,
        failed=metrics.failed,
        lag_seconds=metrics.lag_seconds,
    )


def run_once(
    session: Session,
    sink: EventSink,
    *,
    owner: str | None = None,
    limit: int = 50,
    lease_seconds: int = 30,
    metrics: RelayMetrics | None = None,
) -> RelayMetrics:
    metrics = metrics or RelayMetrics()
    owner = owner or f"relay-{uuid4()}"
    rows = claim_batch(session, owner=owner, limit=limit, lease_seconds=lease_seconds)
    metrics.attempts += sum(row.attempts for row in rows)
    deliver_claimed(session, sink, rows, metrics)
    collect_metrics(session, metrics)
    return metrics
