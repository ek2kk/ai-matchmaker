from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency
from ai_dating.matching.service import unmatch
from ai_dating.messaging.service import list_matches

router = APIRouter()


@router.get("/v1/matches")
def get_matches(
    request: Request,
    db: Session = Depends(get_db),
    state: str = Query(default="active"),
    limit: int = Query(default=20, ge=1, le=20),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_matches(db, account, state=state, limit=limit, after=after)


@router.post("/v1/matches/{match_id}/unmatch")
def post_unmatch(
    match_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(match_id))
    row, replay = claim_idempotency(
        db,
        scope="matches.unmatch",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return Response(status_code=204)
    unmatch(db, account, match_id)
    row.resource_type = "matches"
    row.resource_id = match_id
    row.response_status = 204
    return Response(status_code=204)
