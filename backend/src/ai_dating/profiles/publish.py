from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.errors import AppError
from ai_dating.onboarding.steps import load_preferences, load_profile
from ai_dating.profiles.activation import approved_photo_count, maybe_activate
from ai_dating.profiles.embeddings import embedding_status, enqueue_embeddings
from ai_dating.profiles.models import Profile
from ai_dating.profiles.service import owner_profile_view
from ai_dating.recommendations.enqueue import enqueue_generation


def publish_view(db: Session, account: Account, profile: Profile) -> dict:
    status = embedding_status(db, profile)
    if profile.activated_at is None:
        state = "profile_activation_pending"
    elif status["status"] in {"queued", "running"}:
        state = "generation_pending"
    else:
        state = "active"
    return {
        "status": state,
        "activated_at": None
        if profile.activated_at is None
        else profile.activated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "embedding": status,
        "profile": owner_profile_view(db, account, profile),
    }


def publish_profile(db: Session, account: Account, now: datetime) -> dict:
    if account.onboarding_completed_at is None:
        raise AppError(422, "validation_error", "Onboarding is incomplete.")
    profile = load_profile(db, account.account_id)
    if profile is None:
        raise AppError(422, "validation_error", "Onboarding is incomplete.")
    prefs = load_preferences(db, account.account_id)
    if prefs is None:
        raise AppError(422, "validation_error", "Onboarding is incomplete.")
    settings = load_settings()
    maybe_activate(db, settings, account, profile, now, producer="api")
    if profile.activated_at is None:
        if approved_photo_count(db, profile.profile_id) < 1:
            raise AppError(422, "validation_error", "Add an approved photo first.")
        raise AppError(422, "validation_error", "Profile is not ready to publish.")
    enqueue_embeddings(db, profile, now)
    enqueue_generation(
        db,
        profile=profile,
        prefs=prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    db.flush()
    return publish_view(db, account, profile)
