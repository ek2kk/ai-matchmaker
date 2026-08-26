from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.errors import AppError, request_id_of
from ai_dating.idempotency import claim_idempotency
from ai_dating.privacy.service import append_consent, patch_privacy, privacy_view

router = APIRouter()


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str
    policy_version: str
    decision: str


class PrivacyPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    discoverable: bool | None = None
    show_distance: bool | None = None
    allow_ai_matching: bool | None = None
    allow_product_analytics: bool | None = None


@router.get("/v1/privacy")
def get_privacy(
    request: Request,
    db: Session = Depends(get_db),
    consent_id: UUID | None = None,
    account_id: UUID | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    if account_id is not None and account_id != account.account_id:
        raise AppError(404, "not_found", "Not found.")
    return privacy_view(db, account, consent_id)


@router.post("/v1/consents")
def post_consent(
    body: ConsentIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(body.purpose, body.policy_version, body.decision)
    row, replay = claim_idempotency(
        db,
        scope="consents.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.resource_id is not None:
        return privacy_view(db, account, None)
    consent = append_consent(
        db,
        account,
        purpose=body.purpose,
        policy_version=body.policy_version,
        decision=body.decision,
        request_id=request_id_of(),
    )
    row.resource_type = "consents"
    row.resource_id = consent.consent_id
    row.response_status = 200
    row.response_body = {"consent_id": str(consent.consent_id)}
    return privacy_view(db, account, None)


@router.patch("/v1/privacy")
def patch_privacy_route(
    body: PrivacyPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return patch_privacy(
        db,
        account,
        expected_version=body.expected_version,
        discoverable=body.discoverable,
        show_distance=body.show_distance,
        allow_ai_matching=body.allow_ai_matching,
        allow_product_analytics=body.allow_product_analytics,
        request_id=request_id_of(),
    )
