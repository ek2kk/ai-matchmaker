from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ai_dating.auth.crypto import request_fingerprint
from ai_dating.config import Settings
from ai_dating.deps import get_actor, get_db, require_idempotency_key
from ai_dating.errors import AppError
from ai_dating.idempotency import claim_idempotency
from ai_dating.media.schemas import PhotoPatchIn, UploadIntentIn
from ai_dating.media.service import (
    complete_upload,
    create_upload_intent,
    delete_photo,
    get_local_object,
    list_photos,
    patch_photo,
    put_local_object,
)

router = APIRouter()
local_router = APIRouter()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/v1/profile/photos/upload-intents")
def post_upload_intent(
    body: UploadIntentIn,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(
        body.content_type, str(body.byte_size), body.content_sha256
    )
    row, replay = claim_idempotency(
        db,
        scope="profile.photos.intent",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = create_upload_intent(db, _settings(request), account, body)
    row.resource_type = "photo_upload_intents"
    row.resource_id = UUID(result["upload_intent_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.post("/v1/profile/photos/{upload_intent_id}/complete")
def post_complete(
    upload_intent_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> dict:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(upload_intent_id))
    row, replay = claim_idempotency(
        db,
        scope="profile.photos.complete",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay and row.response_body:
        return row.response_body
    result = complete_upload(db, _settings(request), account, upload_intent_id)
    row.resource_type = "profile_photos"
    row.resource_id = UUID(result["photo_id"])
    row.response_status = 200
    row.response_body = result
    return result


@router.get("/v1/profile/photos")
def get_photos(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return list_photos(db, _settings(request), account)


@router.patch("/v1/profile/photos/{photo_id}")
def patch_photo_route(
    photo_id: UUID,
    body: PhotoPatchIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    account, _sess = get_actor(request, db)
    return patch_photo(db, _settings(request), account, photo_id, body)


@router.delete("/v1/profile/photos/{photo_id}")
def delete_photo_route(
    photo_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Depends(require_idempotency_key),
) -> Response:
    account, _sess = get_actor(request, db)
    digest = request_fingerprint(str(photo_id))
    row, replay = claim_idempotency(
        db,
        scope="profile.photos.delete",
        key=key,
        request_hash=digest,
        account_id=account.account_id,
    )
    if replay:
        return Response(status_code=204)
    delete_photo(db, _settings(request), account, photo_id)
    row.resource_type = "profile_photos"
    row.resource_id = photo_id
    row.response_status = 204
    return Response(status_code=204)


@local_router.put("/v1/media/uploads/{token}")
async def put_upload(token: str, request: Request) -> Response:
    settings = _settings(request)
    if settings.object_storage_backend != "local":
        raise AppError(404, "not_found", "Not found.")
    body = await request.body()
    put_local_object(settings, token, body, request.headers.get("content-type", ""))
    return Response(status_code=204)


@local_router.get("/v1/media/objects/{token}")
def get_object(token: str, request: Request) -> Response:
    settings = _settings(request)
    if settings.object_storage_backend != "local":
        raise AppError(404, "not_found", "Not found.")
    body = get_local_object(settings, token)
    return Response(content=body, media_type="image/jpeg")
