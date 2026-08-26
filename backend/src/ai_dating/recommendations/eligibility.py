from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import any_, exists, func, literal, or_, select, true
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.matching.models import Like
from ai_dating.media.models import ProfilePhoto
from ai_dating.onboarding.validation import years_old
from ai_dating.privacy.models import PrivacyControls
from ai_dating.profiles.models import DatingPreferences, Profile, ProfileEmbedding
from ai_dating.recommendations.constants import (
    ACTIVITY_DAYS,
    MAX_ELIGIBLE,
)
from ai_dating.recommendations.models import RecommendationExposure
from ai_dating.safety.models import Block


class EligibilityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class EligibleCandidate:
    account_id: UUID
    profile_id: UUID
    profile_version: int
    preferences_version: int
    gender_code: str
    search_mode: str
    relationship_goal_code: str | None
    city_code: str
    completion_percent: int
    max_distance_km: int
    last_active_at: datetime
    age: int
    distance_km: float


@dataclass(frozen=True)
class ActorSnapshot:
    account_id: UUID
    profile_id: UUID
    profile_version: int
    preferences_version: int
    gender_code: str
    search_mode: str
    relationship_goal_code: str | None
    city_code: str
    age: int
    age_min: int
    age_max: int
    max_distance_km: int
    accepted_gender_codes: tuple[str, ...]
    city_codes: tuple[str, ...]
    relationship_goal_codes: tuple[str, ...]


def _now() -> datetime:
    return datetime.now(UTC)


def load_actor(
    db: Session, account_id: UUID
) -> tuple[Account, Profile, DatingPreferences, ActorSnapshot] | None:
    account = db.get(Account, account_id)
    profile = db.scalar(select(Profile).where(Profile.account_id == account_id))
    prefs = db.get(DatingPreferences, account_id)
    privacy = db.get(PrivacyControls, account_id)
    if (
        account is None
        or profile is None
        or prefs is None
        or privacy is None
        or account.deleted_at is not None
        or profile.deleted_at is not None
        or account.date_of_birth is None
        or account.status in {"paused", "suspended", "deleted", "deletion_pending"}
        or profile.activated_at is None
        or profile.visibility != "eligible"
        or profile.moderation_state != "approved"
        or not privacy.discoverable
        or not privacy.allow_ai_matching
    ):
        return None
    snapshot = ActorSnapshot(
        account_id=account.account_id,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        preferences_version=prefs.version,
        gender_code=profile.gender_code,
        search_mode=profile.search_mode,
        relationship_goal_code=profile.relationship_goal_code,
        city_code=profile.city_code,
        age=years_old(account.date_of_birth),
        age_min=prefs.age_min,
        age_max=prefs.age_max,
        max_distance_km=prefs.max_distance_km,
        accepted_gender_codes=tuple(prefs.accepted_gender_codes),
        city_codes=tuple(prefs.city_codes),
        relationship_goal_codes=tuple(prefs.relationship_goal_codes),
    )
    return account, profile, prefs, snapshot


def eligible_sql(
    actor: ActorSnapshot, *, now: datetime | None = None, skip_exposure: bool = False
):
    now = now or _now()
    cutoff = now - timedelta(days=ACTIVITY_DAYS)
    cand_account = Account.__table__.alias("cand_account")
    cand_profile = Profile.__table__.alias("cand_profile")
    cand_prefs = DatingPreferences.__table__.alias("cand_prefs")
    cand_privacy = PrivacyControls.__table__.alias("cand_privacy")
    actor_profile = Profile.__table__.alias("actor_profile")
    cand_age = func.date_part(
        "year", func.age(func.current_date(), cand_account.c.date_of_birth)
    )
    limit_m = (
        func.least(literal(actor.max_distance_km), cand_prefs.c.max_distance_km)
        * 1000.0
    )
    goal_ok = or_(
        literal(actor.search_mode) != "dating",
        cand_profile.c.relationship_goal_code.in_(actor.relationship_goal_codes)
        & (
            literal(actor.relationship_goal_code)
            == any_(cand_prefs.c.relationship_goal_codes)
        ),
    )
    return (
        select(
            cand_account.c.account_id,
            cand_profile.c.profile_id,
            cand_profile.c.version,
            cand_prefs.c.version.label("preferences_version"),
            cand_profile.c.gender_code,
            cand_profile.c.search_mode,
            cand_profile.c.relationship_goal_code,
            cand_profile.c.city_code,
            cand_profile.c.completion_percent,
            cand_prefs.c.max_distance_km,
            cand_account.c.last_active_at,
            cand_age.label("age"),
            (
                func.ST_Distance(actor_profile.c.location, cand_profile.c.location)
                / 1000.0
            ).label("distance_km"),
        )
        .select_from(cand_profile)
        .join(cand_account, cand_account.c.account_id == cand_profile.c.account_id)
        .join(cand_prefs, cand_prefs.c.account_id == cand_account.c.account_id)
        .join(cand_privacy, cand_privacy.c.account_id == cand_account.c.account_id)
        .join(actor_profile, actor_profile.c.profile_id == actor.profile_id)
        .where(
            cand_account.c.account_id != actor.account_id,
            cand_account.c.deleted_at.is_(None),
            cand_account.c.status.notin_(
                ("onboarding", "paused", "suspended", "deleted", "deletion_pending")
            ),
            cand_account.c.last_active_at >= cutoff,
            cand_account.c.date_of_birth.is_not(None),
            cand_profile.c.deleted_at.is_(None),
            cand_profile.c.visibility == "eligible",
            cand_profile.c.moderation_state == "approved",
            cand_profile.c.activated_at.is_not(None),
            cand_privacy.c.discoverable.is_(True),
            cand_privacy.c.allow_ai_matching.is_(True),
            cand_profile.c.search_mode == actor.search_mode,
            cand_prefs.c.search_mode == actor.search_mode,
            cand_profile.c.gender_code.in_(actor.accepted_gender_codes),
            literal(actor.gender_code) == any_(cand_prefs.c.accepted_gender_codes),
            cand_profile.c.city_code.in_(actor.city_codes),
            literal(actor.city_code) == any_(cand_prefs.c.city_codes),
            cand_age >= actor.age_min,
            cand_age <= actor.age_max,
            literal(actor.age) >= cand_prefs.c.age_min,
            literal(actor.age) <= cand_prefs.c.age_max,
            func.ST_DWithin(actor_profile.c.location, cand_profile.c.location, limit_m),
            goal_ok,
            exists(
                select(1).where(
                    ProfilePhoto.profile_id == cand_profile.c.profile_id,
                    ProfilePhoto.deleted_at.is_(None),
                    ProfilePhoto.moderation_state == "approved",
                )
            ),
            true()
            if skip_exposure
            else ~exists(
                select(1).where(
                    RecommendationExposure.owner_account_id == actor.account_id,
                    RecommendationExposure.candidate_account_id
                    == cand_account.c.account_id,
                )
            ),
            ~exists(
                select(1).where(
                    Block.ended_at.is_(None),
                    or_(
                        (Block.blocker_account_id == actor.account_id)
                        & (Block.blocked_account_id == cand_account.c.account_id),
                        (Block.blocker_account_id == cand_account.c.account_id)
                        & (Block.blocked_account_id == actor.account_id),
                    ),
                )
            ),
            ~exists(
                select(1).where(
                    Like.actor_account_id == actor.account_id,
                    Like.subject_account_id == cand_account.c.account_id,
                    Like.state == "active",
                )
            ),
        )
        .limit(MAX_ELIGIBLE + 1)
    )


def eligible_candidates(
    db: Session,
    actor: ActorSnapshot,
    *,
    now: datetime | None = None,
    skip_exposure: bool = False,
) -> list[EligibleCandidate]:
    rows = db.execute(eligible_sql(actor, now=now, skip_exposure=skip_exposure)).all()
    if len(rows) > MAX_ELIGIBLE:
        raise EligibilityError("pool_too_large")
    return [
        EligibleCandidate(
            account_id=row.account_id,
            profile_id=row.profile_id,
            profile_version=row.version,
            preferences_version=row.preferences_version,
            gender_code=row.gender_code,
            search_mode=row.search_mode,
            relationship_goal_code=row.relationship_goal_code,
            city_code=row.city_code,
            completion_percent=row.completion_percent,
            max_distance_km=row.max_distance_km,
            last_active_at=row.last_active_at,
            age=int(row.age),
            distance_km=float(row.distance_km),
        )
        for row in rows
    ]


def current_embeddings(
    db: Session,
    profiles: list[tuple[UUID, int, str]],
    *,
    model_version: str,
    projection_schema_version: str,
) -> dict[tuple[UUID, str], ProfileEmbedding]:
    if not profiles:
        return {}
    profile_ids = [profile_id for profile_id, _version, _kind in profiles]
    versions = {profile_id: version for profile_id, version, _kind in profiles}
    kinds = {kind for _profile_id, _version, kind in profiles}
    rows = list(
        db.scalars(
            select(ProfileEmbedding).where(
                ProfileEmbedding.profile_id.in_(profile_ids),
                ProfileEmbedding.kind.in_(kinds),
                ProfileEmbedding.model_version == model_version,
                ProfileEmbedding.projection_schema_version == projection_schema_version,
            )
        )
    )
    out: dict[tuple[UUID, str], ProfileEmbedding] = {}
    for row in rows:
        if row.source_version != versions.get(row.profile_id):
            continue
        out[(row.profile_id, row.kind)] = row
    return out
