from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.client import extraction_model_version
from ai_dating.ai.schema import JOB_TYPE_EXTRACT
from ai_dating.config import load_settings
from ai_dating.errors import AppError
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.onboarding.steps import load_preferences, load_profile, record_step
from ai_dating.onboarding.validation import (
    city_code,
    gender_code,
    orientation_code,
    prompt_code,
    public_area_code,
    relationship_goal_code,
    require_21_plus,
    search_mode,
    validate_answer_text,
    validate_bio,
    validate_display_name,
    validate_location,
)
from ai_dating.onboarding.vocab import (
    DEFAULT_CITY_CODE,
    DEFAULT_PUBLIC_AREA,
    DEFAULT_RELATIONSHIP_STATUS,
    DEFAULT_SEARCH_MODE,
    MOSCOW_LATITUDE,
    MOSCOW_LONGITUDE,
)
from ai_dating.profiles.models import DatingPreferences, Profile, ProfileAnswer
from ai_dating.recommendations.enqueue import enqueue_generation


def _now() -> datetime:
    return datetime.now(UTC)


def location_point(latitude: float, longitude: float):
    lat, lon = validate_location(latitude, longitude)
    return func.ST_GeogFromText(f"SRID=4326;POINT({lon} {lat})")


def location_payload(db: Session, profile: Profile | None) -> dict | None:
    if profile is None:
        return None
    row = db.execute(
        select(
            func.ST_Y(cast(Profile.location, Geometry)),
            func.ST_X(cast(Profile.location, Geometry)),
        ).where(Profile.profile_id == profile.profile_id)
    ).one()
    return {"latitude": float(row[0]), "longitude": float(row[1])}


def active_answers(db: Session, profile_id: UUID) -> list[ProfileAnswer]:
    return list(
        db.scalars(
            select(ProfileAnswer).where(
                ProfileAnswer.profile_id == profile_id,
                ProfileAnswer.deleted_at.is_(None),
            )
        )
    )


def answers_payload(db: Session, profile: Profile | None) -> list[dict]:
    if profile is None:
        return []
    return [
        {
            "answer_id": str(row.answer_id),
            "prompt_code": row.prompt_code,
            "answer_text": row.answer_text,
            "visibility": row.visibility,
            "version": row.version,
        }
        for row in active_answers(db, profile.profile_id)
    ]


def owner_profile_view(db: Session, account: Account, profile: Profile | None) -> dict:
    return {
        "profile_id": str(profile.profile_id) if profile else None,
        "version": profile.version if profile else 0,
        "display_name": profile.display_name if profile else None,
        "bio": profile.bio if profile else None,
        "gender_code": profile.gender_code if profile else None,
        "orientation_code": profile.orientation_code if profile else None,
        "search_mode": profile.search_mode if profile else None,
        "relationship_goal_code": profile.relationship_goal_code if profile else None,
        "relationship_status": profile.relationship_status if profile else None,
        "city_code": profile.city_code if profile else None,
        "public_area_code": profile.public_area_code if profile else None,
        "location": location_payload(db, profile),
        "date_of_birth": account.date_of_birth.isoformat()
        if account.date_of_birth
        else None,
        "visibility": profile.visibility if profile else "hidden",
        "moderation_state": profile.moderation_state if profile else "pending",
        "activated_at": None
        if profile is None or profile.activated_at is None
        else profile.activated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "answers": answers_payload(db, profile),
    }


def owner_preferences_view(prefs: DatingPreferences | None) -> dict:
    if prefs is None:
        return {
            "version": 0,
            "search_mode": None,
            "accepted_gender_codes": [],
            "age_min": None,
            "age_max": None,
            "max_distance_km": None,
            "city_codes": [],
            "relationship_goal_codes": [],
        }
    return {
        "version": prefs.version,
        "search_mode": prefs.search_mode,
        "accepted_gender_codes": list(prefs.accepted_gender_codes),
        "age_min": prefs.age_min,
        "age_max": prefs.age_max,
        "max_distance_km": prefs.max_distance_km,
        "city_codes": list(prefs.city_codes),
        "relationship_goal_codes": list(prefs.relationship_goal_codes),
    }


def require_profile(db: Session, account: Account) -> Profile:
    profile = load_profile(db, account.account_id)
    if profile is None:
        raise AppError(404, "not_found", "Not found.")
    return profile


def expect_version(
    current: int,
    expected: int,
    message: str = "Profile changed; reload and retry.",
) -> None:
    if current != expected:
        raise AppError(
            409,
            "version_conflict",
            message,
            details={"current_version": current},
        )


def bump_profile(profile: Profile, now: datetime) -> None:
    profile.version += 1
    profile.updated_at = now


def _resolved_goal(mode: str, raw_goal: str | None, current: str | None) -> str | None:
    if mode == "friendship":
        if raw_goal:
            raise AppError(
                422,
                "validation_error",
                "Relationship goal is only used for dating.",
                details={
                    "fields": {"relationship_goal_code": "Leave empty for friendship."}
                },
            )
        return None
    goal = raw_goal if raw_goal is not None else current
    if goal is None:
        raise AppError(
            422,
            "validation_error",
            "Complete required profile fields.",
            details={"fields": {"relationship_goal_code": "This field is required."}},
        )
    return relationship_goal_code(goal)


def apply_self_fields(profile: Profile, body) -> bool:
    changed = False
    mode = profile.search_mode
    if body.search_mode is not None:
        mode = search_mode(body.search_mode)
        if mode != profile.search_mode:
            profile.search_mode = mode
            changed = True
    if body.display_name is not None:
        name = validate_display_name(body.display_name)
        if name != profile.display_name:
            profile.display_name = name
            changed = True
    if body.gender_code is not None:
        code = gender_code(body.gender_code)
        if code != profile.gender_code:
            profile.gender_code = code
            changed = True
    if body.orientation_code is not None:
        code = orientation_code(body.orientation_code)
        if code != profile.orientation_code:
            profile.orientation_code = code
            changed = True
    if body.search_mode is not None or body.relationship_goal_code is not None:
        goal = _resolved_goal(
            mode,
            body.relationship_goal_code,
            profile.relationship_goal_code
            if body.relationship_goal_code is None
            else None,
        )
        if goal != profile.relationship_goal_code:
            profile.relationship_goal_code = goal
            changed = True
    if body.city_code is not None:
        code = city_code(body.city_code)
        if code != profile.city_code:
            profile.city_code = code
            changed = True
    if body.public_area_code is not None:
        code = public_area_code(body.public_area_code)
        if code != profile.public_area_code:
            profile.public_area_code = code
            changed = True
    if body.location is not None:
        profile.location = location_point(
            body.location.latitude, body.location.longitude
        )
        changed = True
    return changed


def create_profile(db: Session, account: Account, body, now: datetime) -> Profile:
    missing = [
        name
        for name, value in (
            ("display_name", body.display_name),
            ("gender_code", body.gender_code),
            ("orientation_code", body.orientation_code),
        )
        if value is None
    ]
    if missing:
        raise AppError(
            422,
            "validation_error",
            "Complete required profile fields.",
            details={"fields": {name: "This field is required." for name in missing}},
        )
    mode = search_mode(body.search_mode or DEFAULT_SEARCH_MODE)
    goal = _resolved_goal(mode, body.relationship_goal_code, None)
    loc = body.location
    profile = Profile(
        profile_id=uuid4(),
        account_id=account.account_id,
        display_name=validate_display_name(body.display_name),
        bio=None,
        gender_code=gender_code(body.gender_code),
        orientation_code=orientation_code(body.orientation_code),
        search_mode=mode,
        relationship_goal_code=goal,
        relationship_status=DEFAULT_RELATIONSHIP_STATUS,
        city_code=city_code(body.city_code or DEFAULT_CITY_CODE),
        location=location_point(
            loc.latitude if loc else MOSCOW_LATITUDE,
            loc.longitude if loc else MOSCOW_LONGITUDE,
        ),
        public_area_code=public_area_code(body.public_area_code or DEFAULT_PUBLIC_AREA),
        visibility="hidden",
        moderation_state="pending",
        activated_at=None,
        completion_percent=0,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(profile)
    db.flush()
    return profile


def set_date_of_birth(
    account: Account, dob, profile: Profile | None, now: datetime
) -> bool:
    require_21_plus(dob)
    if account.date_of_birth == dob:
        return False
    account.date_of_birth = dob
    account.updated_at = now
    if profile is not None:
        bump_profile(profile, now)
    return True


def upsert_answers(db: Session, profile: Profile, answers: list, now: datetime) -> bool:
    changed = False
    existing = {row.prompt_code: row for row in active_answers(db, profile.profile_id)}
    touched: list[ProfileAnswer] = []
    for item in answers:
        code = prompt_code(item.prompt_code)
        text = validate_answer_text(item.answer_text)
        row = existing.get(code)
        if row is None:
            row = ProfileAnswer(
                answer_id=uuid4(),
                profile_id=profile.profile_id,
                prompt_code=code,
                answer_text=text,
                visibility="eligible_only",
                version=1,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            db.add(row)
            touched.append(row)
            changed = True
            continue
        if row.answer_text != text:
            row.answer_text = text
            row.version += 1
            row.updated_at = now
            touched.append(row)
            changed = True
    if touched:
        db.flush()
        settings = load_settings()
        for row in touched:
            enqueue_job(
                db,
                job_type=JOB_TYPE_EXTRACT,
                dedup_key=(
                    f"{JOB_TYPE_EXTRACT}:{row.answer_id}:{row.version}:"
                    f"{settings.extraction_prompt_version}:"
                    f"{extraction_model_version(settings)}"
                ),
                payload={
                    "answer_id": str(row.answer_id),
                    "answer_version": row.version,
                    "prompt_version": settings.extraction_prompt_version,
                    "model_version": extraction_model_version(settings),
                },
                now=now,
                max_attempts=settings.extraction_max_attempts,
            )
    return changed


def patch_owner_profile(db: Session, account: Account, body) -> dict:
    profile = require_profile(db, account)
    expect_version(profile.version, body.expected_version)
    now = _now()
    changed = False
    if body.display_name is not None:
        name = validate_display_name(body.display_name)
        if name != profile.display_name:
            profile.display_name = name
            changed = True
    if body.bio is not None:
        bio = validate_bio(body.bio)
        if bio != profile.bio:
            profile.bio = bio
            changed = True
    if body.answers is not None:
        if upsert_answers(db, profile, body.answers, now):
            changed = True
    if changed:
        bump_profile(profile, now)
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
                now=now,
                trigger_code="profile_updated",
            )
    return owner_profile_view(db, account, profile)
