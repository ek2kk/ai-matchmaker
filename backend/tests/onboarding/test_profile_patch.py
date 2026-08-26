from fastapi.testclient import TestClient

from tests.onboarding.helpers import (
    DOB_YOUNG,
    account,
    auth_of,
    profile_body,
)


def test_stale_expected_version_returns_409(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    created = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert created.status_code == 200
    stale = client.patch(
        "/v1/onboarding/profile",
        json=profile_body(0, display_name="Sam"),
        headers=auth,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "version_conflict"
    assert stale.json()["error"]["details"]["current_version"] == 1


def test_dob_under_21_rejected(client: TestClient):
    acc = account(client)
    response = client.patch(
        "/v1/onboarding/profile",
        json={"expected_version": 0, "date_of_birth": DOB_YOUNG},
        headers=auth_of(acc),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "date_of_birth" in response.json()["error"]["details"]["fields"]


def test_unknown_fields_rejected(client: TestClient):
    acc = account(client)
    response = client.patch(
        "/v1/onboarding/profile",
        json={"expected_version": 0, "rank_score": 9},
        headers=auth_of(acc),
    )
    assert response.status_code == 422


def test_owner_projection_excludes_other_account(client: TestClient):
    a = account(client)
    b = account(client)
    stolen = client.get(
        f"/v1/onboarding?account_id={a['account_id']}",
        headers=auth_of(b),
    )
    assert stolen.status_code == 404
    own = client.get("/v1/onboarding", headers=auth_of(b))
    assert own.status_code == 200
    assert own.json()["profile"]["version"] == 0
    assert own.json()["profile"]["location"] is None
