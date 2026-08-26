from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.onboarding.models import OnboardingStepCompletion
from ai_dating.onboarding.validation import years_old
from ai_dating.onboarding.vocab import FLOW_VERSION, SELF_MIN_AGE, STEP_CODES
from ai_dating.privacy.models import Consent
from ai_dating.profiles.models import DatingPreferences, Profile


def _versions(
    profile: Profile | None, prefs: DatingPreferences | None
) -> tuple[int | None, int | None]:
    return (
        profile.version if profile is not None else None,
        prefs.version if prefs is not None else None,
    )


def _step_event(
    account_id: UUID,
    step_code: str,
    profile_version: int | None,
    preferences_version: int | None,
) -> dict:
    return {
        "event_name": "onboarding_step_completed",
        "schema_version": 1,
        "producer": "api",
        "owner": "onboarding",
        "actor_account_id": str(account_id),
        "subject_account_id": None,
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": None,
        "conversation_id": None,
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": {
            "flow_version": FLOW_VERSION,
            "step_code": step_code,
            "profile_version": profile_version,
            "preferences_version": preferences_version,
        },
    }


def record_step(
    db: Session,
    account: Account,
    step_code: str,
    *,
    profile: Profile | None,
    prefs: DatingPreferences | None,
) -> None:
    if step_code not in STEP_CODES:
        raise AppError(422, "validation_error", "Invalid request.")
    profile_version, preferences_version = _versions(profile, prefs)
    now = datetime.now(UTC)
    stmt = (
        insert(OnboardingStepCompletion)
        .values(
            account_id=account.account_id,
            flow_version=FLOW_VERSION,
            step_code=step_code,
            completed_at=now,
            profile_version=profile_version,
            preferences_version=preferences_version,
        )
        .on_conflict_do_nothing(
            index_elements=["account_id", "flow_version", "step_code"]
        )
        .returning(OnboardingStepCompletion.step_code)
    )
    if db.scalar(stmt) is None:
        return
    enqueue_event(
        db,
        _step_event(
            account.account_id, step_code, profile_version, preferences_version
        ),
    )


def _granted(db: Session, account_id: UUID, purpose: str) -> bool:
    row = db.scalar(
        select(Consent)
        .where(Consent.account_id == account_id, Consent.purpose == purpose)
        .order_by(Consent.occurred_at.desc())
        .limit(1)
    )
    return row is not None and row.decision == "granted"


def load_profile(db: Session, account_id: UUID) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.account_id == account_id))


def load_preferences(db: Session, account_id: UUID) -> DatingPreferences | None:
    return db.scalar(
        select(DatingPreferences).where(DatingPreferences.account_id == account_id)
    )


def maybe_record_account_step(db: Session, account: Account) -> None:
    if account.date_of_birth is None or years_old(account.date_of_birth) < SELF_MIN_AGE:
        return
    if not _granted(db, account.account_id, "terms_privacy"):
        return
    if not _granted(db, account.account_id, "ai_matching"):
        return
    record_step(
        db,
        account,
        "account",
        profile=load_profile(db, account.account_id),
        prefs=load_preferences(db, account.account_id),
    )
