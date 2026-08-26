from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import Settings
from ai_dating.errors import request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.media.models import ProfilePhoto
from ai_dating.onboarding.steps import load_preferences
from ai_dating.profiles.embeddings import enqueue_embeddings
from ai_dating.profiles.models import Profile
from ai_dating.recommendations.enqueue import enqueue_generation


def _now() -> datetime:
    return datetime.now(UTC)


def approved_photo_count(db: Session, profile_id) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ProfilePhoto)
            .where(
                ProfilePhoto.profile_id == profile_id,
                ProfilePhoto.deleted_at.is_(None),
                ProfilePhoto.moderation_state == "approved",
            )
        )
        or 0
    )


def hide_without_photos(profile: Profile, count: int) -> None:
    if count == 0 and profile.visibility == "eligible":
        profile.visibility = "hidden"


def maybe_activate(
    db: Session,
    settings: Settings,
    account: Account,
    profile: Profile,
    now: datetime | None = None,
    *,
    producer: str = "api",
) -> None:
    now = now or _now()
    count = approved_photo_count(db, profile.profile_id)
    hide_without_photos(profile, count)
    if account.onboarding_completed_at is None or count < 1:
        return
    if settings.media_auto_approve:
        profile.moderation_state = "approved"
    if profile.moderation_state != "approved":
        return
    first = profile.activated_at is None
    if first:
        profile.activated_at = now
        started = account.onboarding_completed_at
        latency = max(0, int((now - started).total_seconds()))
        enqueue_event(
            db,
            {
                "event_name": "profile_activated",
                "schema_version": 1,
                "producer": producer,
                "owner": "profiles",
                "actor_account_id": None,
                "subject_account_id": str(account.account_id),
                "recommendation_batch_id": None,
                "recommendation_item_id": None,
                "match_id": None,
                "conversation_id": None,
                "request_id": request_id_of() or "local",
                "experiment_assignments": {},
                "privacy_classification": "product_pseudonymous",
                "properties": {
                    "profile_version": profile.version,
                    "activation_latency_seconds": latency,
                },
            },
        )
    profile.visibility = "eligible"
    profile.updated_at = now
    enqueue_embeddings(db, profile, now)
    prefs = load_preferences(db, account.account_id)
    if prefs is not None:
        enqueue_generation(
            db,
            profile=profile,
            prefs=prefs,
            now=now,
            trigger_code="onboarding_complete" if first else "profile_updated",
        )
