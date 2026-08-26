from fastapi.testclient import TestClient
from tests.ai.helpers import drain_jobs
from tests.media.helpers import upload_photo
from tests.onboarding.helpers import account, auth_of, key
from tests.onboarding.test_complete import _finish_user_gates


def test_photo_approval_activates_profile(client: TestClient):
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
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["profile"]["activated_at"] is not None
    assert state["profile"]["visibility"] == "eligible"
    assert state["profile"]["moderation_state"] == "approved"
