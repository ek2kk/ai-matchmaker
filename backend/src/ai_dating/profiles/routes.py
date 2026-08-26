from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.errors import AppError
from ai_dating.idempotency import claim_idempotency
from ai_dating.onboarding.steps import load_profile
from ai_dating.profiles.facts import create_manual_fact, list_facts, review_fact
from ai_dating.profiles.public import get_public_profile, list_public_profiles
from ai_dating.profiles.publish import publish_profile
from ai_dating.profiles.schemas import FactCreateIn, FactReviewIn, ProfilePatchIn
from ai_dating.profiles.service import owner_profile_view, patch_owner_profile

router = APIRouter()


@router.get("/v1/profiles")
def list_profiles(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=50),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_public_profiles(db, account.account_id, limit=limit, after=after)


@router.get("/v1/profiles/{profile_id}")
def get_other_profile(
    profile_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return get_public_profile(db, account.account_id, profile_id)


@router.get("/v1/profile")
def get_profile(
    request: Request,
    db: Session = Depends(get_db),
    profile_id: UUID | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    profile = load_profile(db, account.account_id)
    if profile is None:
        raise AppError(404, "not_found", "Not found.")
    if profile_id is not None and profile_id != profile.profile_id:
        raise AppError(404, "not_found", "Not found.")
    return owner_profile_view(db, account, profile)


@router.patch("/v1/profile")
def patch_profile(
    body: ProfilePatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return patch_owner_profile(db, account, body)


@router.get("/v1/profile/facts")
def get_facts(
    request: Request,
    db: Session = Depends(get_db),
    state: str = Query(default="current"),
    limit: int = Query(default=20, ge=1, le=50),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_facts(db, account, state=state, limit=limit, after=after)


@router.post("/v1/profile/facts")
def post_fact(
    body: FactCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        body.fact_code, body.value, str(body.profile_side), str(body.visibility)
    )
    row, replay = claim_idempotency(
        db,
        scope="profile.facts.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = create_manual_fact(db, account, body)
    row.resource_type = "profile_facts"
    row.resource_id = UUID(result["fact_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/profile/facts/{fact_id}/review")
def post_fact_review(
    fact_id: UUID,
    body: FactReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(fact_id), body.decision, str(body.value), str(body.visibility)
    )
    row, replay = claim_idempotency(
        db,
        scope="profile.facts.review",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = review_fact(db, account, fact_id, body)
    row.resource_type = "profile_facts"
    row.resource_id = fact_id
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/profile/publish")
def post_publish(
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint("profile-publish")
    row, replay = claim_idempotency(
        db,
        scope="profile.publish",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = publish_profile(db, account, datetime.now(UTC))
    row.resource_type = "profiles"
    profile_id = result["profile"]["profile_id"]
    row.resource_id = UUID(profile_id) if profile_id else account.account_id
    row.response_status = 200
    row.response_body = result
    return result
