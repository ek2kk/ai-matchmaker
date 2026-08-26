from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.ai.helpers import drain_jobs
from tests.media.helpers import jpeg_bytes, upload_photo
from tests.onboarding.helpers import account, auth_of, key
from tests.onboarding.test_complete import _finish_user_gates

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.media.images import decode_image
from ai_dating.media.models import ProfilePhoto
from ai_dating.profiles.models import Profile


def _complete_onboarding(client: TestClient, auth: dict) -> None:
    profile_version, prefs_version = _finish_user_gates(client, auth)
    done = client.post(
        "/v1/onboarding/complete",
        json={
            "expected_profile_version": profile_version,
            "expected_preferences_version": prefs_version,
        },
        headers={**auth, **key()},
    )
    assert done.status_code == 202


def test_upload_processes_and_activates(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    photo = upload_photo(client, auth, jpeg_bytes(exif=True))
    assert photo["moderation_state"] == "pending"
    drain_jobs()
    listed = client.get("/v1/profile/photos", headers=auth).json()["items"]
    assert len(listed) == 1
    assert listed[0]["moderation_state"] == "approved"
    preview = client.get(listed[0]["preview_url"])
    assert preview.status_code == 200
    decoded = decode_image(preview.content)
    assert dict(decoded.getexif()) == {}
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["profile"]["activated_at"] is not None
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        names = {
            row.event_name
            for row in session.scalars(select(OutboxEvent))
            if row.payload.get("subject_account_id") == acc["account_id"]
        }
        assert "profile_activated" in names
        row = session.scalar(select(ProfilePhoto))
        assert row is not None
        assert row.derived_object_key is not None


def test_upload_rejects_wrong_owner(client: TestClient):
    first = account(client)
    other = account(client)
    auth = auth_of(first)
    _complete_onboarding(client, auth)
    body = jpeg_bytes()
    digest = __import__("hashlib").sha256(body).hexdigest()
    intent = client.post(
        "/v1/profile/photos/upload-intents",
        json={
            "content_type": "image/jpeg",
            "byte_size": len(body),
            "content_sha256": digest,
        },
        headers={**auth, **key()},
    )
    assert intent.status_code == 200
    stolen = client.post(
        f"/v1/profile/photos/{intent.json()['upload_intent_id']}/complete",
        json={},
        headers={**auth_of(other), **key()},
    )
    assert stolen.status_code == 404


def test_upload_rejects_hash_mismatch(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    body = jpeg_bytes()
    intent = client.post(
        "/v1/profile/photos/upload-intents",
        json={
            "content_type": "image/jpeg",
            "byte_size": len(body),
            "content_sha256": "ab" * 32,
        },
        headers={**auth, **key()},
    )
    assert intent.status_code == 200
    client.put(
        intent.json()["upload_url"],
        content=body,
        headers={"Content-Type": "image/jpeg"},
    )
    done = client.post(
        f"/v1/profile/photos/{intent.json()['upload_intent_id']}/complete",
        json={},
        headers={**auth, **key()},
    )
    assert done.status_code == 422


def test_upload_rejects_oversize(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    response = client.post(
        "/v1/profile/photos/upload-intents",
        json={
            "content_type": "image/jpeg",
            "byte_size": 11 * 1024 * 1024,
            "content_sha256": "a" * 64,
        },
        headers={**auth, **key()},
    )
    assert response.status_code == 422


def test_delete_hides_profile_without_photos(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    photo = upload_photo(client, auth)
    drain_jobs()
    deleted = client.delete(
        f"/v1/profile/photos/{photo['photo_id']}",
        headers={**auth, **key()},
    )
    assert deleted.status_code == 204
    drain_jobs()
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        profile = session.scalar(
            select(Profile).where(Profile.account_id == acc["account_id"])
        )
        assert profile is not None
        assert profile.visibility == "hidden"


def test_swap_photo_positions(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    first = upload_photo(client, auth, jpeg_bytes((200, 30, 30)))
    second = upload_photo(client, auth, jpeg_bytes((30, 200, 30)))
    assert first["position"] == 0
    assert second["position"] == 1
    moved = client.patch(
        f"/v1/profile/photos/{second['photo_id']}",
        json={"expected_version": second["version"], "position": 0},
        headers=auth,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["position"] == 0
    listed = {
        row["photo_id"]: row
        for row in client.get("/v1/profile/photos", headers=auth).json()["items"]
    }
    assert listed[second["photo_id"]]["position"] == 0
    assert listed[first["photo_id"]]["position"] == 1


def test_publish_without_photo_is_422(client: TestClient):

    acc = account(client)
    auth = auth_of(acc)
    _complete_onboarding(client, auth)
    published = client.post("/v1/profile/publish", json={}, headers={**auth, **key()})
    assert published.status_code == 422
