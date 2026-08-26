from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.errors import AppError
from ai_dating.media.service import approved_photo_urls
from ai_dating.onboarding.validation import years_old
from ai_dating.onboarding.vocab import SELF_PROMPT_CODES
from ai_dating.privacy.models import PrivacyControls
from ai_dating.profiles.models import Profile
from ai_dating.profiles.service import active_answers
from ai_dating.safety.service import block_filter, blocked_either_way

_PAGE = 50


def _cursor_id(after: str | None) -> UUID | None:
    if not after:
        return None
    try:
        return UUID(after)
    except ValueError:
        raise AppError(422, "validation_error", "Invalid request.") from None


def _visible():
    return (
        Profile.deleted_at.is_(None),
        Account.deleted_at.is_(None),
        Account.status == "active",
        Account.date_of_birth.is_not(None),
        Profile.activated_at.is_not(None),
        Profile.visibility == "eligible",
        Profile.moderation_state == "approved",
        PrivacyControls.discoverable.is_(True),
    )


def public_card(account: Account, profile: Profile) -> dict:
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
    }


def public_profile(db: Session, account: Account, profile: Profile) -> dict:
    card = public_card(account, profile)
    card["bio"] = profile.bio
    card["answers"] = [
        {
            "answer_id": str(row.answer_id),
            "prompt_code": row.prompt_code,
            "answer_text": row.answer_text,
        }
        for row in active_answers(db, profile.profile_id)
        if row.prompt_code in SELF_PROMPT_CODES and row.visibility != "private"
    ]
    card["photo_urls"] = approved_photo_urls(db, load_settings(), profile.profile_id)
    return card


def list_public_profiles(
    db: Session,
    actor_id: UUID,
    *,
    limit: int = _PAGE,
    after: str | None = None,
) -> dict:
    bound = min(max(limit, 1), _PAGE)
    stmt = (
        select(Profile, Account)
        .join(Account, Account.account_id == Profile.account_id)
        .join(PrivacyControls, PrivacyControls.account_id == Account.account_id)
        .where(*_visible(), block_filter(actor_id))
        .order_by(Profile.activated_at.desc(), Profile.profile_id.desc())
    )
    marker_id = _cursor_id(after)
    if marker_id is not None:
        marker = db.get(Profile, marker_id)
        if marker is None or marker.activated_at is None:
            raise AppError(404, "not_found", "Not found.")
        stmt = stmt.where(
            (Profile.activated_at < marker.activated_at)
            | (
                (Profile.activated_at == marker.activated_at)
                & (Profile.profile_id < marker.profile_id)
            )
        )
    rows = list(db.execute(stmt.limit(bound + 1)).all())
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        next_cursor = str(rows[-1][0].profile_id)
    return {
        "items": [public_card(account, profile) for profile, account in rows],
        "next_cursor": next_cursor,
    }


def get_public_profile(db: Session, actor_id: UUID, profile_id: UUID) -> dict:
    row = db.execute(
        select(Profile, Account)
        .join(Account, Account.account_id == Profile.account_id)
        .join(PrivacyControls, PrivacyControls.account_id == Account.account_id)
        .where(Profile.profile_id == profile_id, *_visible())
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Not found.")
    profile, account = row
    if blocked_either_way(db, actor_id, account.account_id):
        raise AppError(404, "not_found", "Not found.")
    return public_profile(db, account, profile)


__all__ = ["get_public_profile", "list_public_profiles"]
