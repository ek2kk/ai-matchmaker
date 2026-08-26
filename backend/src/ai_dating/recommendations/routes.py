from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency
from ai_dating.recommendations.delivery import current_batch_response
from ai_dating.recommendations.feedback import (
    record_feedback,
    record_impression,
    record_open,
    refresh_current,
)
from ai_dating.recommendations.schemas import FeedbackIn, RefreshIn, SurfaceIn

router = APIRouter()


@router.get("/v1/recommendation-batches/current")
def get_current_batch(request: Request, db: Session = Depends(get_db)):
    account, _sess = get_actor(request, db)
    return current_batch_response(db, account)


@router.post("/v1/recommendation-items/{item_id}/impression")
def post_impression(
    item_id: UUID,
    body: SurfaceIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(item_id), body.surface)
    row, replay = claim_idempotency(
        db,
        scope="recommendations.impression",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = record_impression(db, account, item_id, body.surface)
    row.resource_type = "recommendation_exposures"
    row.resource_id = UUID(result["exposure_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/recommendation-items/{item_id}/open")
def post_open(
    item_id: UUID,
    body: SurfaceIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(item_id), body.surface)
    row, replay = claim_idempotency(
        db,
        scope="recommendations.open",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = record_open(db, account, item_id, body.surface)
    row.resource_type = "recommendation_actions"
    row.resource_id = UUID(result["action_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/recommendation-items/{item_id}/feedback")
def post_feedback(
    item_id: UUID,
    body: FeedbackIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(item_id), body.action, body.reason_code or "")
    row, replay = claim_idempotency(
        db,
        scope="recommendations.feedback",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = record_feedback(db, account, item_id, body.action, body.reason_code)
    row.resource_type = "recommendation_actions"
    row.resource_id = UUID(result["action_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/recommendation-batches/current/refresh")
def post_refresh(
    body: RefreshIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
):
    del body
    account, _sess = get_actor(request, db)
    digest = request_fingerprint("refresh")
    row, replay = claim_idempotency(
        db,
        scope="recommendations.refresh",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return JSONResponse(
            status_code=row.response_status or 202, content=row.response_body
        )
    status, result = refresh_current(db, account)
    row.resource_type = "recommendation_batches"
    row.response_status = status
    row.response_body = result
    return JSONResponse(status_code=status, content=result)
