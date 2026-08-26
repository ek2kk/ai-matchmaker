from fastapi.testclient import TestClient
from tests.ai.helpers import drain_jobs
from tests.media.helpers import upload_photo
from tests.onboarding.helpers import account, auth_of, key
from tests.onboarding.test_complete import _finish_user_gates


def test_invalid_bytes_are_rejected(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile_version, prefs_version = _finish_user_gates(client, auth)
    client.post(
        "/v1/onboarding/complete",
        json={
            "expected_profile_version": profile_version,
            "expected_preferences_version": prefs_version,
        },
        headers={**auth, **key()},
    )
    upload_photo(client, auth, b"not-an-image", content_type="image/jpeg")
    drain_jobs()
    listed = client.get("/v1/profile/photos", headers=auth).json()["items"]
    assert listed[0]["moderation_state"] == "rejected"
