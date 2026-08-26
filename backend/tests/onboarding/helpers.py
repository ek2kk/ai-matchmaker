from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

PASSWORD = "correct-horse-1"
DOB_OK = "2000-01-15"
DOB_YOUNG = "2010-06-01"


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def account(client: TestClient) -> dict:
    response = client.post(
        "/v1/auth/local/register",
        json={"login": f"u{uuid4().hex[:12]}", "password": PASSWORD},
        headers=key(),
    )
    assert response.status_code == 200
    return response.json()


def auth_of(acc: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {acc['session_token']}"}


def profile_body(version: int = 0, **overrides) -> dict:
    body = {
        "expected_version": version,
        "display_name": "Alex",
        "gender_code": "woman",
        "orientation_code": "heterosexual",
        "search_mode": "dating",
        "relationship_goal_code": "serious_relationship",
        "city_code": "moscow",
        "date_of_birth": DOB_OK,
    }
    body.update(overrides)
    return body


def prefs_body(version: int = 0, **overrides) -> dict:
    body = {
        "expected_version": version,
        "search_mode": "dating",
        "accepted_gender_codes": ["man"],
        "age_min": 21,
        "age_max": 35,
        "max_distance_km": 25,
        "city_codes": ["moscow"],
        "relationship_goal_codes": ["serious_relationship"],
    }
    body.update(overrides)
    return body


def prompt_answers(
    text: str = "I like travel, fitness, walking and restaurants.",
) -> list[dict]:
    return [
        {"prompt_code": "self_about", "answer_text": text},
        {"prompt_code": "partner_who", "answer_text": text},
    ]
