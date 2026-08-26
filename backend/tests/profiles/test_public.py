from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.profiles.models import ProfileAnswer
from tests.onboarding.helpers import account, auth_of
from tests.recommendations.helpers import seed_person

pytestmark = [pytest.mark.postgres]

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    engine = create_sync_engine(settings)
    with Session(engine) as session:
        yield session
        session.commit()


def _add_answers(db: Session, profile_id) -> None:
    db.add(
        ProfileAnswer(
            answer_id=uuid4(),
            profile_id=profile_id,
            prompt_code="self_about",
            answer_text="I cook and walk in the centre.",
            visibility="matching_only",
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
            deleted_at=None,
        )
    )
    db.add(
        ProfileAnswer(
            answer_id=uuid4(),
            profile_id=profile_id,
            prompt_code="self_weekend",
            answer_text="Secret weekend plan.",
            visibility="private",
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
            deleted_at=None,
        )
    )
    db.add(
        ProfileAnswer(
            answer_id=uuid4(),
            profile_id=profile_id,
            prompt_code="partner_who",
            answer_text="Looking for someone quiet.",
            visibility="eligible_only",
            version=1,
            created_at=_NOW,
            updated_at=_NOW,
            deleted_at=None,
        )
    )


def test_directory_requires_auth(client: TestClient):
    assert client.get("/v1/profiles").status_code == 401


def test_lists_eligible_public_cards_and_hides_private_fields(
    client: TestClient, db: Session
):
    now = datetime.now(UTC)
    _shown_acc, shown, _ = seed_person(db, gender="woman", last_active=now)
    _hidden_acc, hidden, _ = seed_person(
        db, gender="man", visibility="hidden", last_active=now
    )
    db.flush()
    _add_answers(db, shown.profile_id)
    db.commit()
    actor = account(client)
    auth = auth_of(actor)
    listed = client.get("/v1/profiles?limit=50", headers=auth)
    assert listed.status_code == 200
    ids = {item["profile_id"] for item in listed.json()["items"]}
    after = listed.json()["next_cursor"]
    while after:
        page = client.get(f"/v1/profiles?limit=50&after={after}", headers=auth)
        assert page.status_code == 200
        ids.update(item["profile_id"] for item in page.json()["items"])
        after = page.json()["next_cursor"]
    assert str(shown.profile_id) in ids
    assert str(hidden.profile_id) not in ids
    card = next(
        item
        for item in listed.json()["items"]
        if item["profile_id"] == str(shown.profile_id)
    )
    assert card["display_name"] == "Test"
    assert card["age"] == 26
    assert "date_of_birth" not in card
    assert "location" not in card
    assert "account_id" not in card
    assert "moderation_state" not in card
    assert "answers" not in card
    detail = client.get(f"/v1/profiles/{shown.profile_id}", headers=auth)
    assert detail.status_code == 200
    body = detail.json()
    assert body["age"] == 26
    assert body["bio"] is None
    assert {row["prompt_code"] for row in body["answers"]} == {"self_about"}
    assert "date_of_birth" not in body
    assert "location" not in body
    hidden_get = client.get(f"/v1/profiles/{hidden.profile_id}", headers=auth)
    assert hidden_get.status_code == 404


def test_directory_cursor_pages(client: TestClient, db: Session):
    now = datetime.now(UTC)
    _first_acc, first, _ = seed_person(db, gender="woman", last_active=now)
    _second_acc, second, _ = seed_person(db, gender="man", last_active=now)
    db.commit()
    actor = account(client)
    wanted = {str(first.profile_id), str(second.profile_id)}
    found: set[str] = set()
    after = None
    for _ in range(8):
        query = "/v1/profiles?limit=1"
        if after:
            query += f"&after={after}"
        response = client.get(query, headers=auth_of(actor))
        assert response.status_code == 200
        payload = response.json()
        found.update(item["profile_id"] for item in payload["items"])
        if wanted <= found:
            break
        after = payload["next_cursor"]
        if after is None:
            break
    assert wanted <= found
