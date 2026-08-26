from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.events.models import OutboxEvent
from ai_dating.profiles.models import Profile, ProfileEmbedding
from tests.ai.helpers import drain_jobs
from tests.media.helpers import upload_photo
from tests.onboarding.helpers import account, auth_of, key
from tests.onboarding.test_complete import _finish_user_gates


def test_publish_activates_and_builds_embeddings(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
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
    upload_photo(client, auth)
    drain_jobs()
    published = client.post("/v1/profile/publish", json={}, headers={**auth, **key()})
    assert published.status_code == 200
    body = published.json()
    assert body["activated_at"] is not None
    assert body["status"] in {"generation_pending", "active"}
    assert body["embedding"]["status"] in {"queued", "running", "succeeded"}
    drain_jobs()
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["profile"]["activated_at"] is not None
    assert state["status"] == "active"
    assert state["embedding"]["status"] == "succeeded"
    engine = create_sync_engine(load_settings())
    with Session(engine) as session:
        profile = session.scalar(
            select(Profile).where(Profile.account_id == acc["account_id"])
        )
        assert profile is not None
        assert profile.visibility == "eligible"
        assert profile.moderation_state == "approved"
        kinds = {
            row.kind
            for row in session.scalars(
                select(ProfileEmbedding).where(
                    ProfileEmbedding.profile_id == profile.profile_id
                )
            )
        }
        assert kinds == {"self", "desired_partner"}
        names = {
            row.event_name
            for row in session.scalars(select(OutboxEvent))
            if row.payload.get("subject_account_id") == acc["account_id"]
            or row.payload.get("actor_account_id") == acc["account_id"]
        }
        assert "profile_activated" in names


def test_publish_before_complete_is_422(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    response = client.post("/v1/profile/publish", json={}, headers={**auth, **key()})
    assert response.status_code == 422
