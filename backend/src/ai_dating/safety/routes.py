from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency
from ai_dating.safety.schemas import BlockIn, ReportIn
from ai_dating.safety.service import create_block, create_report, end_block, list_blocks

router = APIRouter()


@router.post("/v1/blocks")
def post_block(
    body: BlockIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(body.profile_id), str(body.match_id), str(body.reason_code)
    )
    row, replay = claim_idempotency(
        db,
        scope="blocks.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return Response(status_code=204)
    block = create_block(
        db,
        account,
        profile_id=body.profile_id,
        match_id=body.match_id,
        reason_code=body.reason_code,
    )
    row.resource_type = "blocks"
    row.resource_id = block.block_id
    row.response_status = 204
    return Response(status_code=204)


@router.delete("/v1/blocks/{block_id}")
def delete_block(
    block_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(block_id))
    row, replay = claim_idempotency(
        db,
        scope="blocks.delete",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return Response(status_code=204)
    end_block(db, account, block_id)
    row.resource_type = "blocks"
    row.resource_id = block_id
    row.response_status = 204
    return Response(status_code=204)


@router.get("/v1/blocks")
def get_blocks(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=50),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_blocks(db, account, limit=limit, after=after)


@router.post("/v1/reports")
def post_report(
    body: ReportIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(body.profile_id),
        str(body.message_id),
        body.reason_code,
        body.details or "",
    )
    row, replay = claim_idempotency(
        db,
        scope="reports.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = create_report(
        db,
        account,
        profile_id=body.profile_id,
        message_id=body.message_id,
        reason_code=body.reason_code,
        details=body.details,
    )
    row.resource_type = "reports"
    row.resource_id = UUID(result["report_id"])
    row.response_status = 200
    row.response_body = result
    return result
