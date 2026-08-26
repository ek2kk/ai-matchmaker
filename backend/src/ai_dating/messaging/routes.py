from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.idempotency import claim_idempotency
from ai_dating.messaging.schemas import MessageIn, ReadIn
from ai_dating.messaging.service import (
    get_message,
    list_conversations,
    list_messages,
    mark_read,
    send_message,
)

router = APIRouter()


@router.get("/v1/conversations")
def get_conversations(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=20),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_conversations(db, account, limit=limit, after=after)


@router.get("/v1/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=50),
    after: str | None = None,
) -> dict:
    account, _sess = get_actor(request, db)
    return list_messages(db, account, conversation_id, limit=limit, after=after)


@router.post("/v1/conversations/{conversation_id}/messages")
def post_message(
    conversation_id: UUID,
    body: MessageIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        str(conversation_id), str(body.client_message_id), body.body
    )
    row, replay = claim_idempotency(
        db,
        scope="messages.create",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = send_message(
        db,
        request.app.state.settings,
        account,
        conversation_id,
        client_message_id=body.client_message_id,
        body=body.body,
    )
    row.resource_type = "messages"
    row.resource_id = UUID(result["message_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.get("/v1/conversations/{conversation_id}/messages/{message_id}")
def get_one_message(
    conversation_id: UUID,
    message_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return get_message(db, account, conversation_id, message_id)


@router.post("/v1/conversations/{conversation_id}/read")
def post_read(
    conversation_id: UUID,
    body: ReadIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(conversation_id), str(body.last_read_message_id))
    row, replay = claim_idempotency(
        db,
        scope="messages.read",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return Response(status_code=204)
    mark_read(db, account, conversation_id, body.last_read_message_id)
    row.resource_type = "conversation_members"
    row.resource_id = conversation_id
    row.response_status = 204
    return Response(status_code=204)
