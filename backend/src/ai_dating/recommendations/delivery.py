from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.errors import AppError
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.models import Profile
from ai_dating.recommendations.constants import JOB_TYPE_GENERATE
from ai_dating.recommendations.eligibility import (
    EligibilityError,
    eligible_candidates,
    load_actor,
)
from ai_dating.recommendations.enqueue import enqueue_generation
from ai_dating.recommendations.models import (
    RecommendationAction,
    RecommendationBatch,
    RecommendationItem,
)
from ai_dating.recommendations.snapshots import (
    delivery_profile_from_snapshot,
    snapshot_photos_current,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pending(db: Session, account_id: UUID) -> bool:
    rows = db.scalars(
        select(BackgroundJob).where(
            BackgroundJob.job_type == JOB_TYPE_GENERATE,
            BackgroundJob.status.in_(("queued", "running")),
        )
    )
    wanted = str(account_id)
    return any(
        isinstance(job.payload, dict) and job.payload.get("account_id") == wanted
        for job in rows
    )


def _latest_ready(
    db: Session, account_id: UUID, now: datetime
) -> RecommendationBatch | None:
    return db.scalar(
        select(RecommendationBatch)
        .where(
            RecommendationBatch.owner_account_id == account_id,
            RecommendationBatch.status == "ready",
            RecommendationBatch.expires_at > now,
        )
        .order_by(RecommendationBatch.ready_at.desc())
        .limit(1)
    )


def load_owned_item(
    db: Session, account_id: UUID, item_id: UUID
) -> tuple[RecommendationBatch, RecommendationItem] | None:
    row = db.execute(
        select(RecommendationItem, RecommendationBatch)
        .join(
            RecommendationBatch,
            RecommendationBatch.recommendation_batch_id
            == RecommendationItem.recommendation_batch_id,
        )
        .where(
            RecommendationItem.recommendation_item_id == item_id,
            RecommendationBatch.owner_account_id == account_id,
        )
    ).one_or_none()
    if row is None:
        return None
    item, batch = row
    return batch, item


def batch_is_current(batch: RecommendationBatch, now: datetime) -> bool:
    return batch.status == "ready" and batch.expires_at > now


def candidate_eligible(db: Session, actor, candidate_id: UUID, now: datetime) -> bool:
    try:
        eligible = {
            row.account_id
            for row in eligible_candidates(db, actor, now=now, skip_exposure=True)
        }
    except EligibilityError:
        return False
    return candidate_id in eligible


def _item_view(db: Session, item: RecommendationItem) -> dict | None:
    account = db.get(Account, item.candidate_account_id)
    profile = db.scalar(
        select(Profile).where(Profile.account_id == item.candidate_account_id)
    )
    if account is None or profile is None:
        return None
    if profile.version != item.candidate_profile_version:
        return None
    raw = item.public_profile_snapshot
    if not isinstance(raw, dict):
        return None
    urls = snapshot_photos_current(db, load_settings(), raw)
    if urls is None:
        return None
    reason = item.reason_snapshot if isinstance(item.reason_snapshot, dict) else None
    return {
        "recommendation_item_id": str(item.recommendation_item_id),
        "rank": item.rank,
        "profile": delivery_profile_from_snapshot(raw, urls),
        "reason": reason,
    }


def current_batch(db: Session, account: Account) -> tuple[int, dict]:
    loaded = load_actor(db, account.account_id)
    if loaded is None:
        raise AppError(404, "not_found", "Not found.")
    _account, profile, prefs, actor = loaded
    now = _now()
    batch = _latest_ready(db, account.account_id, now)
    if batch is None:
        if not _pending(db, account.account_id):
            enqueue_generation(
                db, profile=profile, prefs=prefs, now=now, trigger_code="refill"
            )
        return 202, {
            "recommendation_batch_id": None,
            "status": "pending",
            "expires_at": None,
            "items": [],
        }
    items = list(
        db.scalars(
            select(RecommendationItem)
            .where(
                RecommendationItem.recommendation_batch_id
                == batch.recommendation_batch_id
            )
            .order_by(RecommendationItem.rank)
        )
    )
    try:
        eligible = {
            row.account_id
            for row in eligible_candidates(db, actor, now=now, skip_exposure=True)
        }
    except EligibilityError:
        eligible = set()
    delivered: list[dict] = []
    omitted = False
    for item in items:
        if item.candidate_account_id not in eligible:
            omitted = True
            continue
        view = _item_view(db, item)
        if view is None:
            omitted = True
            continue
        delivered.append(view)
    if delivered:
        states = _action_state(
            db,
            account.account_id,
            [UUID(row["recommendation_item_id"]) for row in delivered],
        )
        for view in delivered:
            view.update(states[UUID(view["recommendation_item_id"])])
    if omitted or not delivered:
        enqueue_generation(
            db, profile=profile, prefs=prefs, now=now, trigger_code="refill"
        )
    status = "ready" if delivered else "insufficient_supply"
    return 200, {
        "recommendation_batch_id": str(batch.recommendation_batch_id),
        "status": status,
        "expires_at": _iso(batch.expires_at),
        "items": delivered,
    }


def _action_state(
    db: Session, account_id: UUID, item_ids: list[UUID]
) -> dict[UUID, dict]:
    out = {item_id: {"opened": False, "decision": None} for item_id in item_ids}
    for row in db.scalars(
        select(RecommendationAction).where(
            RecommendationAction.actor_account_id == account_id,
            RecommendationAction.recommendation_item_id.in_(item_ids),
        )
    ):
        state = out[row.recommendation_item_id]
        if row.action == "open":
            state["opened"] = True
        elif row.action in {"like", "pass"}:
            state["decision"] = row.action
    return out


def current_batch_response(db: Session, account: Account) -> dict | JSONResponse:
    status, body = current_batch(db, account)
    if status != 200:
        return JSONResponse(status_code=status, content=body)
    return body
