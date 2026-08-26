from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import Settings
from ai_dating.media.models import ProfilePhoto
from ai_dating.media.service import approved_photos
from ai_dating.media.storage import open_store
from ai_dating.onboarding.validation import years_old
from ai_dating.onboarding.vocab import SELF_PROMPT_CODES
from ai_dating.profiles.models import Profile
from ai_dating.profiles.service import active_answers
from ai_dating.recommendations.models import RecommendationItem

REASON_LABELS = {
    "shared_goal": "You want similar relationship goals.",
    "prompt_theme": "Your prompts and facts overlap.",
    "similar_intent": "Your desired-partner description is close to theirs.",
    "distance_band": "You are looking in a similar area.",
}
HEURISTIC_REASON_CODES = frozenset(REASON_LABELS)
LLM_REASON_CODES = frozenset({"shared_goal", "prompt_theme", "distance_band"})


def render_reason(codes: list[str]) -> dict | None:
    ordered = [code for code in codes if code in REASON_LABELS]
    if not ordered:
        return None
    return {
        "version": 1,
        "codes": ordered,
        "text": " ".join(REASON_LABELS[code] for code in ordered),
    }


def public_scalar_snapshot(account: Account, profile: Profile) -> dict:
    assert account.date_of_birth is not None
    return {
        "profile_id": str(profile.profile_id),
        "display_name": profile.display_name,
        "age": years_old(account.date_of_birth),
        "gender_code": profile.gender_code,
        "search_mode": profile.search_mode,
        "relationship_goal_code": profile.relationship_goal_code,
        "city_code": profile.city_code,
        "public_area_code": profile.public_area_code,
        "bio": profile.bio,
    }


def item_profile_snapshot(db: Session, account: Account, profile: Profile) -> dict:
    answers = [
        {
            "answer_id": str(row.answer_id),
            "prompt_code": row.prompt_code,
            "answer_text": row.answer_text,
            "version": row.version,
        }
        for row in active_answers(db, profile.profile_id)
        if row.prompt_code in SELF_PROMPT_CODES and row.visibility != "private"
    ]
    photos = [
        {"photo_id": str(row.photo_id), "version": row.version}
        for row in approved_photos(db, profile.profile_id)
    ]
    body = public_scalar_snapshot(account, profile)
    body["answers"] = answers
    body["photos"] = photos
    return body


def snapshot_photos_current(
    db: Session, settings: Settings, snapshot: dict
) -> list[str] | None:
    refs = snapshot.get("photos")
    if not isinstance(refs, list):
        return None
    urls: list[str] = []
    store = open_store(settings)
    expires = int(
        (
            datetime.now(UTC) + timedelta(seconds=settings.media_url_ttl_seconds)
        ).timestamp()
    )
    for ref in refs:
        if not isinstance(ref, dict):
            return None
        try:
            photo_id = UUID(str(ref["photo_id"]))
            version = int(ref["version"])
        except (KeyError, TypeError, ValueError):
            return None
        photo = db.get(ProfilePhoto, photo_id)
        if (
            photo is None
            or photo.deleted_at is not None
            or photo.moderation_state != "approved"
            or photo.version != version
            or not photo.derived_object_key
        ):
            return None
        urls.append(store.download_url(photo.derived_object_key, expires))
    return urls


def delivery_profile_from_snapshot(snapshot: dict, photo_urls: list[str]) -> dict:
    body = {
        key: snapshot[key]
        for key in (
            "profile_id",
            "display_name",
            "age",
            "gender_code",
            "search_mode",
            "relationship_goal_code",
            "city_code",
            "public_area_code",
            "bio",
        )
        if key in snapshot
    }
    body["answers"] = [
        {
            "answer_id": row["answer_id"],
            "prompt_code": row["prompt_code"],
            "answer_text": row["answer_text"],
        }
        for row in snapshot.get("answers") or []
        if isinstance(row, dict)
    ]
    body["photo_urls"] = photo_urls
    return body


def erase_candidate_snapshots(db: Session, account_id: UUID) -> int:
    result = db.execute(
        update(RecommendationItem)
        .where(RecommendationItem.candidate_account_id == account_id)
        .values(public_profile_snapshot=None, reason_snapshot=None)
    )
    return int(result.rowcount or 0)


def rerank_projection(snapshot: dict, scores: dict[str, float]) -> dict:
    return {
        "profile_id": snapshot.get("profile_id"),
        "age": snapshot.get("age"),
        "gender_code": snapshot.get("gender_code"),
        "search_mode": snapshot.get("search_mode"),
        "relationship_goal_code": snapshot.get("relationship_goal_code"),
        "city_code": snapshot.get("city_code"),
        "public_area_code": snapshot.get("public_area_code"),
        "answer_prompt_codes": [
            row.get("prompt_code")
            for row in snapshot.get("answers") or []
            if isinstance(row, dict)
        ],
        "photo_count": len(snapshot.get("photos") or []),
        "scores": {
            name: round(value, 5)
            for name, value in scores.items()
            if name in {"goal", "facts", "distance", "activity", "quality"}
        },
    }
