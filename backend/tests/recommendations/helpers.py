from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.schema import EMBED_DIM, PROJECTION_SCHEMA_VERSION
from ai_dating.media.models import ProfilePhoto
from ai_dating.privacy.models import PrivacyControls
from ai_dating.profiles.models import DatingPreferences, Profile, ProfileEmbedding
from ai_dating.profiles.service import location_point
from ai_dating.recommendations.constants import RANKER_VERSION
from ai_dating.recommendations.models import (
    RecommendationBatch,
    RecommendationExposure,
    RecommendationItem,
)

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def unit_vec(seed: int) -> list[float]:
    values = [((index * 17 + seed) % 97) / 97.0 for index in range(EMBED_DIM)]
    norm = sum(item * item for item in values) ** 0.5
    return [item / norm for item in values]


def seed_person(
    db: Session,
    *,
    gender: str = "woman",
    accepted: list[str] | None = None,
    goal: str = "serious_relationship",
    goals: list[str] | None = None,
    age_min: int = 21,
    age_max: int = 35,
    dob_year: int = 2000,
    search_mode: str = "dating",
    city: str = "moscow",
    cities: list[str] | None = None,
    max_distance_km: int = 25,
    lat: float = 55.75,
    lon: float = 37.62,
    visibility: str = "eligible",
    moderation: str = "approved",
    status: str = "active",
    discoverable: bool = True,
    allow_ai_matching: bool = True,
    last_active: datetime | None = None,
    completion: int = 100,
    embed: bool = True,
    photo: bool = True,
    model_version: str = "gte-base",
) -> tuple[Account, Profile, DatingPreferences]:
    now = last_active or _NOW
    account = Account(
        account_id=uuid4(),
        status=status,
        date_of_birth=datetime(dob_year, 1, 15, tzinfo=UTC).date(),
        last_active_at=now,
        onboarding_completed_at=now,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(account)
    db.flush()
    profile = Profile(
        profile_id=uuid4(),
        account_id=account.account_id,
        display_name="Test",
        bio=None,
        gender_code=gender,
        orientation_code="heterosexual",
        search_mode=search_mode,
        relationship_goal_code=None if search_mode == "friendship" else goal,
        relationship_status="single",
        city_code=city,
        location=location_point(lat, lon),
        public_area_code="moscow_central",
        visibility=visibility,
        moderation_state=moderation,
        activated_at=now,
        completion_percent=completion,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(profile)
    prefs = DatingPreferences(
        account_id=account.account_id,
        search_mode=search_mode,
        accepted_gender_codes=accepted or (["man"] if gender == "woman" else ["woman"]),
        age_min=age_min,
        age_max=age_max,
        max_distance_km=max_distance_km,
        city_codes=cities or [city],
        relationship_goal_codes=[]
        if search_mode == "friendship"
        else (goals or [goal]),
        dealbreakers={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(prefs)
    db.add(
        PrivacyControls(
            account_id=account.account_id,
            discoverable=discoverable,
            show_distance=False,
            allow_ai_matching=allow_ai_matching,
            allow_product_analytics=False,
            version=1,
            updated_at=now,
        )
    )
    db.flush()
    if photo:
        photo_id = uuid4()
        db.add(
            ProfilePhoto(
                photo_id=photo_id,
                profile_id=profile.profile_id,
                object_key=f"photos/{profile.profile_id}/{photo_id}",
                derived_object_key=f"photos/{profile.profile_id}/{photo_id}-derived.jpg",
                position=0,
                moderation_state="approved",
                content_hash="0" * 64,
                content_type="image/jpeg",
                byte_size=128,
                width=32,
                height=24,
                version=1,
                created_at=now,
                moderated_at=now,
                deleted_at=None,
            )
        )
        db.flush()
    if embed:
        for kind, seed in (("self", 1), ("desired_partner", 2)):
            db.add(
                ProfileEmbedding(
                    embedding_id=uuid4(),
                    profile_id=profile.profile_id,
                    kind=kind,
                    source_version=profile.version,
                    model_version=model_version,
                    projection_schema_version=PROJECTION_SCHEMA_VERSION,
                    embedding=unit_vec(seed + (0 if gender == "woman" else 10)),
                    created_at=now,
                )
            )
        db.flush()
    return account, profile, prefs


def seed_exposure(
    db: Session,
    owner_id: UUID,
    candidate_id: UUID,
) -> None:
    now = _NOW
    batch = RecommendationBatch(
        recommendation_batch_id=uuid4(),
        owner_account_id=owner_id,
        status="ready",
        generation_key=f"test:{owner_id}:{candidate_id}",
        batch_schema_version=1,
        input_snapshot={"policy_version": "test"},
        eligibility_version="test",
        ranker_version=RANKER_VERSION,
        prompt_version=None,
        model_version=None,
        fallback_mode="none",
        candidate_count=1,
        item_count=1,
        created_at=now,
        ready_at=now,
        expires_at=now,
    )
    db.add(batch)
    db.flush()
    item = RecommendationItem(
        recommendation_item_id=uuid4(),
        recommendation_batch_id=batch.recommendation_batch_id,
        candidate_account_id=candidate_id,
        item_schema_version=1,
        rank=1,
        final_score=1,
        public_profile_snapshot=None,
        reason_snapshot=None,
        candidate_profile_version=1,
        candidate_embedding_version=None,
        created_at=now,
    )
    db.add(item)
    db.flush()
    db.add(
        RecommendationExposure(
            exposure_id=uuid4(),
            owner_account_id=owner_id,
            candidate_account_id=candidate_id,
            recommendation_item_id=item.recommendation_item_id,
            impressed_at=now,
            client_surface="test",
        )
    )
    db.flush()


def auth_headers(db: Session, account_id: UUID) -> dict[str, str]:
    from ai_dating.auth.sessions import issue_session

    token, _sess = issue_session(db, account_id, 86400)
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def generate_batch(db: Session, profile: Profile, prefs: DatingPreferences) -> None:
    from ai_dating.config import load_settings
    from ai_dating.jobs.claim import claim_jobs
    from ai_dating.jobs.generate_batch import process_generate_job
    from ai_dating.recommendations.constants import JOB_TYPE_GENERATE
    from ai_dating.recommendations.enqueue import enqueue_generation

    now = datetime.now(UTC)
    enqueue_generation(
        db,
        profile=profile,
        prefs=prefs,
        now=now,
        trigger_code="onboarding_complete",
    )
    db.commit()
    settings = load_settings()
    jobs = claim_jobs(
        db,
        limit=8,
        lease_seconds=settings.job_lease_seconds,
        job_types=(JOB_TYPE_GENERATE,),
    )
    with Session(db.get_bind()) as work:
        for job in jobs:
            process_generate_job(work, settings, job)


def seed_pair(
    db: Session,
) -> tuple[
    tuple[Account, Profile, DatingPreferences],
    tuple[Account, Profile, DatingPreferences],
]:
    now = datetime.now(UTC)
    lat = 70.0 + (uuid4().int % 10_000) / 10_000.0
    lon = 20.0 + (uuid4().int % 10_000) / 10_000.0
    alice = seed_person(
        db,
        gender="woman",
        last_active=now,
        lat=lat,
        lon=lon,
        max_distance_km=5,
    )
    bob = seed_person(
        db,
        gender="man",
        accepted=["woman"],
        last_active=now,
        lat=lat,
        lon=lon,
        max_distance_km=5,
    )
    return alice, bob


def seed_ready_item(
    db: Session,
    owner: Account,
    candidate: Account,
    candidate_profile: Profile,
    *,
    rank: int = 1,
) -> RecommendationItem:
    now = datetime.now(UTC)
    batch = RecommendationBatch(
        recommendation_batch_id=uuid4(),
        owner_account_id=owner.account_id,
        status="ready",
        generation_key=f"test:{owner.account_id}:{uuid4()}",
        batch_schema_version=1,
        input_snapshot={"policy_version": "test"},
        eligibility_version="test",
        ranker_version=RANKER_VERSION,
        prompt_version=None,
        model_version=None,
        fallback_mode="none",
        candidate_count=1,
        item_count=1,
        created_at=now,
        ready_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(batch)
    db.flush()
    item = RecommendationItem(
        recommendation_item_id=uuid4(),
        recommendation_batch_id=batch.recommendation_batch_id,
        candidate_account_id=candidate.account_id,
        item_schema_version=1,
        rank=rank,
        final_score=1,
        public_profile_snapshot={
            "profile_id": str(candidate_profile.profile_id),
            "display_name": candidate_profile.display_name,
            "age": 26,
            "gender_code": candidate_profile.gender_code,
            "search_mode": candidate_profile.search_mode,
            "relationship_goal_code": candidate_profile.relationship_goal_code,
            "city_code": candidate_profile.city_code,
            "public_area_code": candidate_profile.public_area_code,
            "bio": None,
            "answers": [],
            "photos": [],
        },
        reason_snapshot=None,
        candidate_profile_version=candidate_profile.version,
        candidate_embedding_version=None,
        created_at=now,
    )
    db.add(item)
    db.flush()
    return item
