from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.audit import write_audit
from ai_dating.events.enqueue import enqueue_event
from ai_dating.onboarding.calibration import calibration_done
from ai_dating.onboarding.models import OnboardingStepCompletion
from ai_dating.onboarding.steps import (
    load_preferences,
    load_profile,
    maybe_record_account_step,
    record_step,
)
from ai_dating.onboarding.validation import (
    accepted_genders,
    city_codes,
    relationship_goals,
    search_mode,
    validate_age_range,
    validate_distance,
    years_old,
)
from ai_dating.onboarding.vocab import (
    DEFAULT_CITY_CODE,
    DEFAULT_SEARCH_MODE,
    DESIRED_PROMPT_CODES,
    FLOW_VERSION,
    SELF_MIN_AGE,
    SELF_PROMPT_CODES,
)
from ai_dating.privacy.models import PRIVACY_POLICY_VERSION
from ai_dating.privacy.service import latest_consents, privacy_view
from ai_dating.profiles.embeddings import embedding_status, enqueue_embeddings
from ai_dating.profiles.facts import extraction_status, facts_reviewed, pending_jobs
from ai_dating.profiles.models import DatingPreferences, Profile
from ai_dating.profiles.service import (
    apply_self_fields,
    bump_profile,
    create_profile,
    expect_version,
    owner_preferences_view,
    owner_profile_view,
    set_date_of_birth,
)
from ai_dating.recommendations.enqueue import enqueue_generation


def _now() -> datetime:
    return datetime.now(UTC)


def _latest_granted(db: Session, account_id: UUID, purpose: str) -> bool:
    for row in latest_consents(db, account_id):
        if row.purpose == purpose:
            return row.decision == "granted"
    return False


def _gates(
    db: Session,
    account: Account,
    profile: Profile | None,
    prefs: DatingPreferences | None,
) -> dict[str, bool]:
    answers = owner_profile_view(db, account, profile)["answers"]
    codes = {row["prompt_code"] for row in answers}
    return {
        "dob_21_plus": account.date_of_birth is not None
        and years_old(account.date_of_birth) >= SELF_MIN_AGE,
        "terms_privacy": _latest_granted(db, account.account_id, "terms_privacy"),
        "ai_matching": _latest_granted(db, account.account_id, "ai_matching"),
        "self_profile": profile is not None,
        "preferences": prefs is not None,
        "prompt_answer": bool(codes & set(SELF_PROMPT_CODES))
        and bool(codes & set(DESIRED_PROMPT_CODES)),
        "facts_reviewed": facts_reviewed(db, profile),
        "calibration_done": calibration_done(db, account.account_id),
        "discoverable": privacy_view(db, account, None)["discoverable"] is True,
    }


def _percent(gates: dict[str, bool]) -> int:
    if not gates:
        return 0
    return round(100 * sum(1 for ok in gates.values() if ok) / len(gates))


def _steps(db: Session, account_id: UUID) -> list[str]:
    rows = db.scalars(
        select(OnboardingStepCompletion).where(
            OnboardingStepCompletion.account_id == account_id,
            OnboardingStepCompletion.flow_version == FLOW_VERSION,
        )
    )
    return [row.step_code for row in rows]


def onboarding_state(db: Session, account: Account) -> dict:
    profile = load_profile(db, account.account_id)
    prefs = load_preferences(db, account.account_id)
    gates = _gates(db, account, profile, prefs)
    completed = account.onboarding_completed_at is not None
    embed = embedding_status(db, profile)
    if not completed:
        status = "in_progress"
    elif profile is None or profile.activated_at is None:
        status = "profile_activation_pending"
    elif embed["status"] in {"queued", "running"}:
        status = "generation_pending"
    else:
        status = "active"
    return {
        "flow_version": FLOW_VERSION,
        "policy_version": PRIVACY_POLICY_VERSION,
        "onboarding_completed": completed,
        "status": status,
        "account_status": account.status,
        "profile": owner_profile_view(db, account, profile),
        "preferences": owner_preferences_view(prefs),
        "privacy": privacy_view(db, account, None),
        "gates": gates,
        "steps_completed": _steps(db, account.account_id),
        "completion_percent": _percent(gates),
        "pending_jobs": pending_jobs(db, profile),
        "extraction": extraction_status(db, profile),
        "embedding": embed,
    }


def patch_onboarding_profile(db: Session, account: Account, body) -> dict:
    profile = load_profile(db, account.account_id)
    current = profile.version if profile is not None else 0
    expect_version(current, body.expected_version)
    now = _now()
    if profile is None:
        has_self = any(
            value is not None
            for value in (
                body.display_name,
                body.gender_code,
                body.orientation_code,
                body.search_mode,
                body.relationship_goal_code,
                body.city_code,
                body.location,
                body.public_area_code,
            )
        )
        if has_self:
            profile = create_profile(db, account, body, now)
            record_step(
                db,
                account,
                "profile",
                profile=profile,
                prefs=load_preferences(db, account.account_id),
            )
        if body.date_of_birth is not None:
            set_date_of_birth(account, body.date_of_birth, None, now)
        maybe_record_account_step(db, account)
        return owner_profile_view(db, account, profile)
    changed = apply_self_fields(profile, body)
    dob_bumped = False
    if body.date_of_birth is not None:
        dob_bumped = set_date_of_birth(account, body.date_of_birth, profile, now)
        if dob_bumped:
            changed = True
    if changed and not dob_bumped:
        profile.version += 1
        profile.updated_at = now
    if changed:
        db.flush()
        prefs = load_preferences(db, account.account_id)
        record_step(
            db,
            account,
            "profile",
            profile=profile,
            prefs=prefs,
        )
        if profile.activated_at is not None and prefs is not None:
            enqueue_generation(
                db,
                profile=profile,
                prefs=prefs,
                now=_now(),
                trigger_code="profile_updated",
            )
    maybe_record_account_step(db, account)
    return owner_profile_view(db, account, profile)


def _create_preferences(
    db: Session, account: Account, body, now: datetime
) -> DatingPreferences:
    missing = [
        name
        for name, value in (
            ("accepted_gender_codes", body.accepted_gender_codes),
            ("age_min", body.age_min),
            ("age_max", body.age_max),
            ("max_distance_km", body.max_distance_km),
        )
        if value is None
    ]
    mode = search_mode(body.search_mode or DEFAULT_SEARCH_MODE)
    if mode == "dating" and body.relationship_goal_codes is None:
        missing.append("relationship_goal_codes")
    if missing:
        raise AppError(
            422,
            "validation_error",
            "Complete required preference fields.",
            details={"fields": {name: "This field is required." for name in missing}},
        )
    age_min, age_max = validate_age_range(body.age_min, body.age_max)
    goals = relationship_goals(
        body.relationship_goal_codes or [],
        allow_empty=mode == "friendship",
    )
    prefs = DatingPreferences(
        account_id=account.account_id,
        search_mode=mode,
        accepted_gender_codes=accepted_genders(body.accepted_gender_codes),
        age_min=age_min,
        age_max=age_max,
        max_distance_km=validate_distance(body.max_distance_km),
        city_codes=city_codes(body.city_codes or [DEFAULT_CITY_CODE]),
        relationship_goal_codes=goals,
        dealbreakers={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(prefs)
    db.flush()
    return prefs


def patch_onboarding_preferences(db: Session, account: Account, body) -> dict:
    prefs = load_preferences(db, account.account_id)
    current = prefs.version if prefs is not None else 0
    expect_version(
        current,
        body.expected_version,
        "Preferences changed; reload and retry.",
    )
    now = _now()
    if prefs is None:
        prefs = _create_preferences(db, account, body, now)
        record_step(
            db,
            account,
            "preferences",
            profile=load_profile(db, account.account_id),
            prefs=prefs,
        )
        return owner_preferences_view(prefs)
    changed = False
    mode = prefs.search_mode
    if body.search_mode is not None:
        mode = search_mode(body.search_mode)
        if mode != prefs.search_mode:
            prefs.search_mode = mode
            changed = True
    if body.accepted_gender_codes is not None:
        codes = accepted_genders(body.accepted_gender_codes)
        if codes != list(prefs.accepted_gender_codes):
            prefs.accepted_gender_codes = codes
            changed = True
    if body.age_min is not None or body.age_max is not None:
        age_min = body.age_min if body.age_min is not None else prefs.age_min
        age_max = body.age_max if body.age_max is not None else prefs.age_max
        age_min, age_max = validate_age_range(age_min, age_max)
        if (age_min, age_max) != (prefs.age_min, prefs.age_max):
            prefs.age_min = age_min
            prefs.age_max = age_max
            changed = True
    if body.max_distance_km is not None:
        km = validate_distance(body.max_distance_km)
        if km != prefs.max_distance_km:
            prefs.max_distance_km = km
            changed = True
    if body.city_codes is not None:
        codes = city_codes(body.city_codes)
        if codes != list(prefs.city_codes):
            prefs.city_codes = codes
            changed = True
    if body.search_mode is not None or body.relationship_goal_codes is not None:
        if mode == "friendship":
            goals = relationship_goals(
                body.relationship_goal_codes or [], allow_empty=True
            )
        else:
            raw = (
                body.relationship_goal_codes
                if body.relationship_goal_codes is not None
                else list(prefs.relationship_goal_codes)
            )
            goals = relationship_goals(raw, allow_empty=False)
        if goals != list(prefs.relationship_goal_codes):
            prefs.relationship_goal_codes = goals
            changed = True
    if changed:
        prefs.version += 1
        prefs.updated_at = now
        db.flush()
        profile = load_profile(db, account.account_id)
        record_step(
            db,
            account,
            "preferences",
            profile=profile,
            prefs=prefs,
        )
        if profile is not None and profile.activated_at is not None:
            bump_profile(profile, now)
            enqueue_embeddings(db, profile, now)
            enqueue_generation(
                db,
                profile=profile,
                prefs=prefs,
                now=now,
                trigger_code="profile_updated",
            )
    return owner_preferences_view(prefs)


def _complete_event(
    account: Account, profile: Profile, prefs: DatingPreferences
) -> dict:
    now = _now()
    duration = max(0, int((now - account.created_at).total_seconds()))
    return {
        "event_name": "onboarding_completed",
        "schema_version": 1,
        "producer": "api",
        "owner": "onboarding",
        "actor_account_id": str(account.account_id),
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
            "profile_version": profile.version,
            "preferences_version": prefs.version,
            "duration_seconds": duration,
        },
    }


def complete_view(db: Session, account: Account) -> dict:
    profile = load_profile(db, account.account_id)
    prefs = load_preferences(db, account.account_id)
    return {
        "status": "profile_activation_pending",
        "flow_version": FLOW_VERSION,
        "profile_version": profile.version if profile else 0,
        "preferences_version": prefs.version if prefs else 0,
        "onboarding_completed_at": None
        if account.onboarding_completed_at is None
        else account.onboarding_completed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def complete_onboarding(db: Session, account: Account, body) -> dict:
    if account.status in {"suspended", "deleted", "deletion_pending"}:
        raise AppError(403, "forbidden", "Account is not eligible.")
    profile = load_profile(db, account.account_id)
    prefs = load_preferences(db, account.account_id)
    if account.onboarding_completed_at is not None:
        return complete_view(db, account)
    current_profile = profile.version if profile is not None else 0
    current_prefs = prefs.version if prefs is not None else 0
    if (
        current_profile != body.expected_profile_version
        or current_prefs != body.expected_preferences_version
    ):
        raise AppError(
            409,
            "version_conflict",
            "Profile changed; reload and retry.",
            details={
                "current_profile_version": current_profile,
                "current_preferences_version": current_prefs,
            },
        )
    gates = _gates(db, account, profile, prefs)
    missing = {
        name: "Required to finish onboarding." for name, ok in gates.items() if not ok
    }
    if missing:
        raise AppError(
            422,
            "validation_error",
            "Onboarding is incomplete.",
            details={"gates": missing},
        )
    assert profile is not None and prefs is not None
    now = _now()
    account.onboarding_completed_at = now
    account.status = "active"
    account.updated_at = now
    profile.completion_percent = 100
    profile.updated_at = now
    enqueue_event(db, _complete_event(account, profile, prefs))
    write_audit(
        db,
        action="onboarding_completed",
        actor_id=account.account_id,
        subject_account_id=account.account_id,
        resource_type="accounts",
        resource_id=account.account_id,
        request_id=request_id_of(),
        metadata={"flow_version": FLOW_VERSION},
    )
    return complete_view(db, account)
