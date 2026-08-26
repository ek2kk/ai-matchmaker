from fastapi.testclient import TestClient

from tests.onboarding.helpers import account, auth_of, prefs_body, profile_body


def test_invalid_age_range_422(client: TestClient):
    acc = account(client)
    response = client.patch(
        "/v1/onboarding/preferences",
        json=prefs_body(0, age_min=40, age_max=21),
        headers=auth_of(acc),
    )
    assert response.status_code == 422


def test_empty_accepted_genders_422(client: TestClient):
    acc = account(client)
    response = client.patch(
        "/v1/onboarding/preferences",
        json=prefs_body(0, accepted_gender_codes=[]),
        headers=auth_of(acc),
    )
    assert response.status_code == 422


def test_orientation_not_copied_to_preferences(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    profile = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert profile.status_code == 200
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["preferences"]["accepted_gender_codes"] == []
    assert state["profile"]["orientation_code"] == "heterosexual"
    prefs = client.patch(
        "/v1/onboarding/preferences",
        json=prefs_body(0, accepted_gender_codes=["woman"]),
        headers=auth,
    )
    assert prefs.status_code == 200
    again = client.patch(
        "/v1/onboarding/profile",
        json={
            "expected_version": profile.json()["version"],
            "orientation_code": "heterosexual",
            "gender_code": "man",
        },
        headers=auth,
    )
    assert again.status_code == 200
    state = client.get("/v1/onboarding", headers=auth).json()
    assert state["preferences"]["accepted_gender_codes"] == ["woman"]
    assert state["profile"]["gender_code"] == "man"
    assert state["profile"]["search_mode"] == "dating"
    assert state["profile"]["city_code"] == "moscow"


def test_friendship_omits_relationship_goal(client: TestClient):
    acc = account(client)
    auth = auth_of(acc)
    created = client.patch(
        "/v1/onboarding/profile",
        json=profile_body(
            0,
            search_mode="friendship",
            relationship_goal_code=None,
        ),
        headers=auth,
    )
    assert created.status_code == 200
    assert created.json()["search_mode"] == "friendship"
    assert created.json()["relationship_goal_code"] is None
    prefs = client.patch(
        "/v1/onboarding/preferences",
        json=prefs_body(
            0,
            search_mode="friendship",
            relationship_goal_codes=[],
        ),
        headers=auth,
    )
    assert prefs.status_code == 200
    assert prefs.json()["search_mode"] == "friendship"
    assert prefs.json()["relationship_goal_codes"] == []
    assert prefs.json()["city_codes"] == ["moscow"]
