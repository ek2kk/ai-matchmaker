from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_dating.errors import request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.privacy.models import BackgroundJob
from ai_dating.profiles.models import DatingPreferences, Profile
from ai_dating.recommendations.constants import (
    DAILY_BATCH_QUOTA,
    JOB_TYPE_GENERATE,
    POLICY_VERSION,
    TRIGGER_CODES,
)
from ai_dating.recommendations.models import RecommendationBatch, RecommendationItem


def generation_key(
    account_id: UUID,
    profile_version: int,
    preferences_version: int,
    *,
    now: datetime,
    quota_slot: int,
) -> str:
    day = now.strftime("%Y-%m-%d")
    return (
        f"{account_id}:{profile_version}:{preferences_version}:"
        f"{POLICY_VERSION}:{day}:{quota_slot}"
    )


def next_quota_slot(
    db: Session,
    account_id: UUID,
    profile_version: int,
    preferences_version: int,
    now: datetime,
) -> int | None:
    for slot in range(DAILY_BATCH_QUOTA):
        key = generation_key(
            account_id,
            profile_version,
            preferences_version,
            now=now,
            quota_slot=slot,
        )
        existing = db.scalar(
            select(RecommendationBatch).where(RecommendationBatch.generation_key == key)
        )
        if existing is None or existing.item_count == 0:
            return slot
    return None


def enqueue_generation(
    db: Session,
    *,
    profile: Profile,
    prefs: DatingPreferences,
    now: datetime,
    trigger_code: str,
) -> UUID | None:
    if profile.activated_at is None:
        return None
    if trigger_code not in TRIGGER_CODES:
        raise ValueError("trigger_code")
    slot = next_quota_slot(db, profile.account_id, profile.version, prefs.version, now)
    if slot is None:
        return None
    key = generation_key(
        profile.account_id,
        profile.version,
        prefs.version,
        now=now,
        quota_slot=slot,
    )
    empty = db.scalar(
        select(RecommendationBatch).where(RecommendationBatch.generation_key == key)
    )
    if empty is not None and empty.item_count == 0:
        db.execute(
            delete(RecommendationItem).where(
                RecommendationItem.recommendation_batch_id
                == empty.recommendation_batch_id
            )
        )
        db.delete(empty)
        db.execute(
            delete(BackgroundJob).where(
                BackgroundJob.dedup_key == f"{JOB_TYPE_GENERATE}:{key}"
            )
        )
        db.flush()
    elif empty is None:
        db.execute(
            delete(BackgroundJob).where(
                BackgroundJob.dedup_key == f"{JOB_TYPE_GENERATE}:{key}",
                BackgroundJob.status.in_(("succeeded", "failed")),
            )
        )
        db.flush()
    job_id = enqueue_job(
        db,
        job_type=JOB_TYPE_GENERATE,
        dedup_key=f"{JOB_TYPE_GENERATE}:{key}",
        payload={
            "account_id": str(profile.account_id),
            "profile_version": profile.version,
            "preferences_version": prefs.version,
            "policy_version": POLICY_VERSION,
            "trigger_code": trigger_code,
            "generation_key": key,
            "quota_slot": slot,
        },
        now=now,
        max_attempts=3,
    )
    if job_id is None:
        return None
    enqueue_event(
        db,
        {
            "event_name": "recommendation_generation_queued",
            "schema_version": 1,
            "producer": "api",
            "owner": "recommendations",
            "actor_account_id": None,
            "subject_account_id": str(profile.account_id),
            "recommendation_batch_id": None,
            "recommendation_item_id": None,
            "match_id": None,
            "conversation_id": None,
            "request_id": request_id_of() or "local",
            "experiment_assignments": {},
            "privacy_classification": "product_pseudonymous",
            "properties": {
                "job_id": str(job_id),
                "trigger_code": trigger_code,
                "profile_version": profile.version,
                "preferences_version": prefs.version,
            },
        },
    )
    return job_id
