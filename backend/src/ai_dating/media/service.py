from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.config import Settings
from ai_dating.errors import AppError
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.media.constants import (
    ALLOWED_TYPES,
    JOB_TYPE_CLEANUP_MEDIA,
    JOB_TYPE_PROCESS_PHOTO,
    MAX_PHOTOS,
)
from ai_dating.media.models import PhotoUploadIntent, ProfilePhoto
from ai_dating.media.storage import ObjectStore, open_store
from ai_dating.onboarding.steps import load_profile
from ai_dating.profiles.activation import maybe_activate
from ai_dating.profiles.models import Profile
from ai_dating.profiles.service import bump_profile, expect_version

_SHA = re.compile(r"^[0-9a-f]{64}$")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store(settings: Settings) -> ObjectStore:
    return open_store(settings)


def _require_profile(db: Session, account: Account) -> Profile:
    profile = load_profile(db, account.account_id)
    if profile is None:
        raise AppError(404, "not_found", "Not found.")
    return profile


def _active_photos(db: Session, profile_id: UUID) -> list[ProfilePhoto]:
    return list(
        db.scalars(
            select(ProfilePhoto)
            .where(
                ProfilePhoto.profile_id == profile_id,
                ProfilePhoto.deleted_at.is_(None),
            )
            .order_by(ProfilePhoto.position, ProfilePhoto.photo_id)
        )
    )


def _next_position(photos: list[ProfilePhoto]) -> int:
    used = {row.position for row in photos}
    for slot in range(MAX_PHOTOS):
        if slot not in used:
            return slot
    raise AppError(422, "validation_error", "Photo limit reached.")


def _photo_view(settings: Settings, photo: ProfilePhoto, now: datetime) -> dict:
    store = _store(settings)
    expires = int((now + timedelta(seconds=settings.media_url_ttl_seconds)).timestamp())
    key = photo.derived_object_key or photo.object_key
    return {
        "photo_id": str(photo.photo_id),
        "position": photo.position,
        "moderation_state": photo.moderation_state,
        "version": photo.version,
        "width": photo.width,
        "height": photo.height,
        "preview_url": store.download_url(key, expires),
        "created_at": _iso(photo.created_at),
    }


def approved_photos(db: Session, profile_id: UUID) -> list[ProfilePhoto]:
    return [
        row
        for row in _active_photos(db, profile_id)
        if row.moderation_state == "approved" and row.derived_object_key
    ]


def approved_photo_urls(db: Session, settings: Settings, profile_id: UUID) -> list[str]:
    now = _now()
    store = _store(settings)
    expires = int((now + timedelta(seconds=settings.media_url_ttl_seconds)).timestamp())
    return [
        store.download_url(row.derived_object_key, expires)
        for row in approved_photos(db, profile_id)
        if row.derived_object_key
    ]


def approved_photo_refs(db: Session, profile_id: UUID) -> list[dict]:
    return [
        {"photo_id": str(row.photo_id), "version": row.version}
        for row in approved_photos(db, profile_id)
    ]


def create_upload_intent(
    db: Session, settings: Settings, account: Account, body
) -> dict:
    profile = _require_profile(db, account)
    content_type = body.content_type.lower()
    if content_type not in ALLOWED_TYPES:
        raise AppError(422, "validation_error", "Unsupported image type.")
    if body.byte_size > settings.photo_max_bytes:
        raise AppError(422, "validation_error", "Image is too large.")
    digest = body.content_sha256.lower()
    if not _SHA.fullmatch(digest):
        raise AppError(422, "validation_error", "Invalid request.")
    now = _now()
    photos = _active_photos(db, profile.profile_id)
    if len(photos) >= MAX_PHOTOS:
        raise AppError(422, "validation_error", "Photo limit reached.")
    cutoff = now - timedelta(days=1)
    used = db.scalar(
        select(func.count())
        .select_from(PhotoUploadIntent)
        .where(
            PhotoUploadIntent.account_id == account.account_id,
            PhotoUploadIntent.created_at >= cutoff,
        )
    )
    if int(used or 0) >= settings.photo_uploads_per_day:
        raise AppError(429, "rate_limited", "Try again later.")
    intent_id = uuid4()
    object_key = f"photos/{account.account_id}/{intent_id}"
    expires = now + timedelta(seconds=settings.upload_intent_ttl_seconds)
    db.add(
        PhotoUploadIntent(
            upload_intent_id=intent_id,
            account_id=account.account_id,
            profile_id=profile.profile_id,
            object_key=object_key,
            content_type=content_type,
            byte_size=body.byte_size,
            content_sha256=digest,
            status="pending",
            photo_id=None,
            expires_at=expires,
            created_at=now,
        )
    )
    store = _store(settings)
    return {
        "upload_intent_id": str(intent_id),
        "upload_url": store.upload_url(
            object_key, content_type, int(expires.timestamp())
        ),
        "expires_at": _iso(expires),
        "headers": {"Content-Type": content_type},
    }


def complete_upload(
    db: Session, settings: Settings, account: Account, intent_id: UUID
) -> dict:
    profile = _require_profile(db, account)
    intent = db.get(PhotoUploadIntent, intent_id)
    if intent is None or intent.account_id != account.account_id:
        raise AppError(404, "not_found", "Not found.")
    now = _now()
    if intent.status == "completed" and intent.photo_id is not None:
        photo = db.get(ProfilePhoto, intent.photo_id)
        if photo is not None:
            return _photo_view(settings, photo, now)
    if intent.status != "pending" or intent.expires_at <= now:
        raise AppError(422, "validation_error", "Upload expired.")
    store = _store(settings)
    stored = store.get(intent.object_key)
    if not stored.exists or stored.body is None:
        raise AppError(422, "validation_error", "Upload is incomplete.")
    if stored.size != intent.byte_size:
        raise AppError(422, "validation_error", "Upload does not match the intent.")
    digest = hashlib.sha256(stored.body).hexdigest()
    if digest != intent.content_sha256:
        raise AppError(422, "validation_error", "Upload does not match the intent.")
    photos = _active_photos(db, profile.profile_id)
    photo = ProfilePhoto(
        photo_id=uuid4(),
        profile_id=profile.profile_id,
        object_key=intent.object_key,
        derived_object_key=None,
        position=_next_position(photos),
        moderation_state="pending",
        content_hash=digest,
        content_type=intent.content_type,
        byte_size=intent.byte_size,
        width=None,
        height=None,
        version=1,
        created_at=now,
        moderated_at=None,
        deleted_at=None,
    )
    db.add(photo)
    db.flush()
    intent.status = "completed"
    intent.photo_id = photo.photo_id
    bump_profile(profile, now)
    enqueue_job(
        db,
        job_type=JOB_TYPE_PROCESS_PHOTO,
        dedup_key=f"{JOB_TYPE_PROCESS_PHOTO}:{photo.photo_id}:{photo.version}",
        payload={
            "photo_id": str(photo.photo_id),
            "photo_version": photo.version,
        },
        now=now,
        max_attempts=3,
    )
    return _photo_view(settings, photo, now)


def list_photos(db: Session, settings: Settings, account: Account) -> dict:
    profile = _require_profile(db, account)
    now = _now()
    return {
        "items": [
            _photo_view(settings, row, now)
            for row in _active_photos(db, profile.profile_id)
        ]
    }


def patch_photo(
    db: Session, settings: Settings, account: Account, photo_id: UUID, body
) -> dict:
    profile = _require_profile(db, account)
    photo = db.get(ProfilePhoto, photo_id)
    if photo is None or photo.profile_id != profile.profile_id or photo.deleted_at:
        raise AppError(404, "not_found", "Not found.")
    expect_version(photo.version, body.expected_version)
    now = _now()
    if photo.position != body.position:
        other = next(
            (
                row
                for row in _active_photos(db, profile.profile_id)
                if row.position == body.position and row.photo_id != photo.photo_id
            ),
            None,
        )
        old_position = photo.position
        if other is None:
            photo.position = body.position
            photo.version += 1
        else:
            # Postgres unique indexes are checked per row, so a one-shot
            # swap of (profile_id, position) collides. Park on -1 first.
            photo.position = -1
            db.flush()
            other.position = old_position
            other.version += 1
            db.flush()
            photo.position = body.position
            photo.version += 1
        bump_profile(profile, now)
    return _photo_view(settings, photo, now)


def delete_photo(
    db: Session, settings: Settings, account: Account, photo_id: UUID
) -> None:
    profile = _require_profile(db, account)
    photo = db.get(ProfilePhoto, photo_id)
    if photo is None or photo.profile_id != profile.profile_id or photo.deleted_at:
        raise AppError(404, "not_found", "Not found.")
    now = _now()
    photo.deleted_at = now
    photo.version += 1
    bump_profile(profile, now)
    maybe_activate(db, settings, account, profile, now, producer="api")
    enqueue_job(
        db,
        job_type=JOB_TYPE_CLEANUP_MEDIA,
        dedup_key=f"{JOB_TYPE_CLEANUP_MEDIA}:{photo.photo_id}",
        payload={
            "photo_id": str(photo.photo_id),
            "object_key": photo.object_key,
            "derived_object_key": photo.derived_object_key,
        },
        now=now,
        max_attempts=8,
    )


def put_local_object(
    settings: Settings, token: str, body: bytes, content_type: str
) -> None:
    from ai_dating.media.storage import local_key_from_upload_token

    if len(body) > settings.photo_max_bytes:
        raise AppError(422, "validation_error", "Image is too large.")
    key = local_key_from_upload_token(settings, token)
    _store(settings).put(key, body, content_type or "application/octet-stream")


def get_local_object(settings: Settings, token: str) -> bytes:
    from ai_dating.media.storage import local_key_from_download_token

    key = local_key_from_download_token(settings, token)
    stored = _store(settings).get(key)
    if not stored.exists or stored.body is None:
        raise AppError(404, "not_found", "Not found.")
    return stored.body
