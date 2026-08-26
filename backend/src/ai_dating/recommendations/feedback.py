from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.matching.service import commit_like, like_view
from ai_dating.recommendations.constants import PASS_REASON_CODES, SURFACES
from ai_dating.recommendations.delivery import (
    _item_view,
    batch_is_current,
    candidate_eligible,
    load_owned_item,
)
from ai_dating.recommendations.eligibility import load_actor
from ai_dating.recommendations.enqueue import enqueue_generation
from ai_dating.recommendations.models import (
    RecommendationAction,
    RecommendationBatch,
    RecommendationExposure,
    RecommendationItem,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _hidden() -> NoReturn:
    raise AppError(404, "not_found", "Not found.")


def _surface(value: str) -> str:
    if value not in SURFACES:
        raise AppError(422, "validation_error", "Invalid request.")
    return value


def _event(
    *,
    event_name: str,
    owner: str,
    actor_id: UUID,
    subject_id: UUID,
    batch: RecommendationBatch,
    item: RecommendationItem,
    properties: dict,
    match_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> dict:
    return {
        "event_name": event_name,
        "schema_version": 1,
        "producer": "api",
        "owner": owner,
        "actor_account_id": str(actor_id),
        "subject_account_id": str(subject_id),
        "recommendation_batch_id": str(batch.recommendation_batch_id),
        "recommendation_item_id": str(item.recommendation_item_id),
        "match_id": None if match_id is None else str(match_id),
        "conversation_id": None if conversation_id is None else str(conversation_id),
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": properties,
    }


def _require_actor(db: Session, account: Account):
    loaded = load_actor(db, account.account_id)
    if loaded is None:
        _hidden()
    return loaded


def _owned(
    db: Session, account_id: UUID, item_id: UUID
) -> tuple[RecommendationBatch, RecommendationItem]:
    loaded = load_owned_item(db, account_id, item_id)
    if loaded is None:
        _hidden()
    return loaded


def _deliverable(
    db, actor, batch: RecommendationBatch, item: RecommendationItem, now: datetime
) -> None:
    if not batch_is_current(batch, now):
        _hidden()
    if not candidate_eligible(db, actor, item.candidate_account_id, now):
        _hidden()
    if _item_view(db, item) is None:
        _hidden()


def _exposure(db: Session, item_id: UUID) -> RecommendationExposure | None:
    return db.scalar(
        select(RecommendationExposure).where(
            RecommendationExposure.recommendation_item_id == item_id
        )
    )


def _action(
    db: Session, item_id: UUID, actor_id: UUID, action: str
) -> RecommendationAction | None:
    return db.scalar(
        select(RecommendationAction).where(
            RecommendationAction.recommendation_item_id == item_id,
            RecommendationAction.actor_account_id == actor_id,
            RecommendationAction.action == action,
        )
    )


def _terminal(
    db: Session, item_id: UUID, actor_id: UUID
) -> RecommendationAction | None:
    return db.scalar(
        select(RecommendationAction).where(
            RecommendationAction.recommendation_item_id == item_id,
            RecommendationAction.actor_account_id == actor_id,
            RecommendationAction.action.in_(("like", "pass")),
        )
    )


def record_impression(
    db: Session, account: Account, item_id: UUID, surface: str
) -> dict:
    surface = _surface(surface)
    loaded = _require_actor(db, account)
    _account, _profile, _prefs, actor = loaded
    batch, item = _owned(db, account.account_id, item_id)
    existing = _exposure(db, item.recommendation_item_id)
    if existing is not None:
        return {
            "exposure_id": str(existing.exposure_id),
            "recommendation_item_id": str(item.recommendation_item_id),
        }
    pair = db.scalar(
        select(RecommendationExposure).where(
            RecommendationExposure.owner_account_id == account.account_id,
            RecommendationExposure.candidate_account_id == item.candidate_account_id,
        )
    )
    if pair is not None:
        raise AppError(409, "already_exposed_elsewhere", "Candidate already exposed.")
    now = _now()
    _deliverable(db, actor, batch, item, now)
    exposure_id = uuid4()
    inserted = db.execute(
        insert(RecommendationExposure)
        .values(
            exposure_id=exposure_id,
            owner_account_id=account.account_id,
            candidate_account_id=item.candidate_account_id,
            recommendation_item_id=item.recommendation_item_id,
            impressed_at=now,
            client_surface=surface,
        )
        .on_conflict_do_nothing()
        .returning(RecommendationExposure.exposure_id)
    ).scalar()
    if inserted is None:
        found = _exposure(db, item.recommendation_item_id)
        if found is not None:
            return {
                "exposure_id": str(found.exposure_id),
                "recommendation_item_id": str(item.recommendation_item_id),
            }
        raise AppError(409, "already_exposed_elsewhere", "Candidate already exposed.")
    enqueue_event(
        db,
        _event(
            event_name="impression",
            owner="recommendations",
            actor_id=account.account_id,
            subject_id=item.candidate_account_id,
            batch=batch,
            item=item,
            properties={
                "surface": surface,
                "rank": item.rank,
                "batch_schema_version": batch.batch_schema_version,
            },
        ),
    )
    return {
        "exposure_id": str(inserted),
        "recommendation_item_id": str(item.recommendation_item_id),
    }


def record_open(db: Session, account: Account, item_id: UUID, surface: str) -> dict:
    surface = _surface(surface)
    loaded = _require_actor(db, account)
    _account, _profile, _prefs, actor = loaded
    batch, item = _owned(db, account.account_id, item_id)
    existing = _action(db, item.recommendation_item_id, account.account_id, "open")
    if existing is not None:
        return {
            "action_id": str(existing.action_id),
            "recommendation_item_id": str(item.recommendation_item_id),
        }
    if _exposure(db, item.recommendation_item_id) is None:
        _hidden()
    now = _now()
    _deliverable(db, actor, batch, item, now)
    action_id = uuid4()
    inserted = db.execute(
        insert(RecommendationAction)
        .values(
            action_id=action_id,
            recommendation_item_id=item.recommendation_item_id,
            actor_account_id=account.account_id,
            action="open",
            reason_code=None,
            created_at=now,
        )
        .on_conflict_do_nothing(
            index_elements=[
                "recommendation_item_id",
                "actor_account_id",
                "action",
            ]
        )
        .returning(RecommendationAction.action_id)
    ).scalar()
    if inserted is None:
        found = _action(db, item.recommendation_item_id, account.account_id, "open")
        if found is None:
            _hidden()
        return {
            "action_id": str(found.action_id),
            "recommendation_item_id": str(item.recommendation_item_id),
        }
    enqueue_event(
        db,
        _event(
            event_name="open",
            owner="recommendations",
            actor_id=account.account_id,
            subject_id=item.candidate_account_id,
            batch=batch,
            item=item,
            properties={
                "action_id": str(inserted),
                "surface": surface,
                "rank": item.rank,
            },
        ),
    )
    return {
        "action_id": str(inserted),
        "recommendation_item_id": str(item.recommendation_item_id),
    }


def record_feedback(
    db: Session,
    account: Account,
    item_id: UUID,
    action: str,
    reason_code: str | None,
) -> dict:
    if action not in {"like", "pass"}:
        raise AppError(422, "validation_error", "Invalid request.")
    if reason_code is not None:
        if action != "pass" or reason_code not in PASS_REASON_CODES:
            raise AppError(422, "validation_error", "Invalid request.")
    loaded = _require_actor(db, account)
    _account, _profile, _prefs, actor = loaded
    batch, item = _owned(db, account.account_id, item_id)
    existing = _terminal(db, item.recommendation_item_id, account.account_id)
    if existing is not None:
        if existing.action != action:
            raise AppError(409, "decision_conflict", "Item already has a decision.")
        if action == "like":
            return like_view(db, existing, item)
        return {
            "action_id": str(existing.action_id),
            "recommendation_item_id": str(item.recommendation_item_id),
            "decision": "pass",
            "match": None,
        }
    if _exposure(db, item.recommendation_item_id) is None:
        _hidden()
    now = _now()
    _deliverable(db, actor, batch, item, now)
    if action == "like":
        return commit_like(db, account, batch, item, now)
    return _record_pass(db, account, batch, item, reason_code, now)


def _record_pass(
    db: Session,
    account: Account,
    batch: RecommendationBatch,
    item: RecommendationItem,
    reason_code: str | None,
    now: datetime,
) -> dict:
    action = RecommendationAction(
        action_id=uuid4(),
        recommendation_item_id=item.recommendation_item_id,
        actor_account_id=account.account_id,
        action="pass",
        reason_code=reason_code,
        created_at=now,
    )
    try:
        with db.begin_nested():
            db.add(action)
            db.flush()
    except IntegrityError:
        existing = _terminal(db, item.recommendation_item_id, account.account_id)
        if existing is None:
            _hidden()
        if existing.action != "pass":
            raise AppError(409, "decision_conflict", "Item already has a decision.")
        return {
            "action_id": str(existing.action_id),
            "recommendation_item_id": str(item.recommendation_item_id),
            "decision": "pass",
            "match": None,
        }
    enqueue_event(
        db,
        _event(
            event_name="pass",
            owner="recommendations",
            actor_id=account.account_id,
            subject_id=item.candidate_account_id,
            batch=batch,
            item=item,
            properties={"action_id": str(action.action_id)},
        ),
    )
    if reason_code is not None:
        enqueue_event(
            db,
            _event(
                event_name="pass_reason",
                owner="recommendations",
                actor_id=account.account_id,
                subject_id=item.candidate_account_id,
                batch=batch,
                item=item,
                properties={
                    "action_id": str(action.action_id),
                    "reason_code": reason_code,
                },
            ),
        )
    return {
        "action_id": str(action.action_id),
        "recommendation_item_id": str(item.recommendation_item_id),
        "decision": "pass",
        "match": None,
    }


def refresh_current(db: Session, account: Account) -> tuple[int, dict]:
    loaded = _require_actor(db, account)
    _account, profile, prefs, actor = loaded
    now = _now()
    batch = db.scalar(
        select(RecommendationBatch)
        .where(
            RecommendationBatch.owner_account_id == account.account_id,
            RecommendationBatch.status == "ready",
            RecommendationBatch.expires_at > now,
        )
        .order_by(RecommendationBatch.ready_at.desc())
        .limit(1)
    )
    if batch is not None and not _consumed(db, actor, batch, now):
        raise AppError(409, "refresh_unavailable", "Current batch is still open.")
    job_id = enqueue_generation(
        db, profile=profile, prefs=prefs, now=now, trigger_code="refill"
    )
    if job_id is None:
        raise AppError(409, "refresh_unavailable", "Refresh is not available.")
    return 202, {
        "recommendation_batch_id": None,
        "status": "pending",
        "expires_at": None,
        "items": [],
    }


def _consumed(db: Session, actor, batch: RecommendationBatch, now: datetime) -> bool:
    items = list(
        db.scalars(
            select(RecommendationItem).where(
                RecommendationItem.recommendation_batch_id
                == batch.recommendation_batch_id
            )
        )
    )
    if not items:
        return True
    decided = {
        row.recommendation_item_id
        for row in db.scalars(
            select(RecommendationAction).where(
                RecommendationAction.actor_account_id == actor.account_id,
                RecommendationAction.action.in_(("like", "pass")),
                RecommendationAction.recommendation_item_id.in_(
                    [item.recommendation_item_id for item in items]
                ),
            )
        )
    }
    for item in items:
        if item.recommendation_item_id in decided:
            continue
        if not candidate_eligible(db, actor, item.candidate_account_id, now):
            continue
        if _item_view(db, item) is None:
            continue
        return False
    return True
