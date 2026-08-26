from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.ai.helpers import drain_jobs
from tests.messaging.helpers import pair_with_match, send
from tests.onboarding.helpers import key

from ai_dating.app import create_app
from ai_dating.config import Settings, load_settings
from ai_dating.events.models import OutboxEvent
from ai_dating.messaging.models import Message
from ai_dating.messaging.service import apply_message_moderation

pytestmark = [pytest.mark.postgres]


def test_held_hidden_from_recipient(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "secret")
    assert sent.status_code == 200
    body = sent.json()
    assert body["moderation_state"] == "held"
    assert body["body"] == "secret"
    assert body["allowed_at"] is None
    history = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=bob_auth,
    )
    assert history.status_code == 200
    assert history.json()["items"] == []
    hidden = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages/{body['message_id']}",
        headers=bob_auth,
    )
    assert hidden.status_code == 404
    own = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages/{body['message_id']}",
        headers=alice_auth,
    )
    assert own.status_code == 200
    assert own.json()["moderation_state"] == "held"


def test_drain_allows_and_recipient_reads(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    send(client, alice_auth, conversation.conversation_id, "hello there")
    drain_jobs()
    history = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=bob_auth,
    )
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) == 1
    assert items[0]["body"] == "hello there"
    assert items[0]["moderation_state"] == "allowed"
    assert items[0]["allowed_at"]
    marked = client.post(
        f"/v1/conversations/{conversation.conversation_id}/read",
        json={"last_read_message_id": items[0]["message_id"]},
        headers={**bob_auth, **key()},
    )
    assert marked.status_code == 204


@pytest.mark.integration
def test_allowed_at_cursor_ignores_created_order(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    first = send(client, alice_auth, conversation.conversation_id, "older")
    second = send(client, alice_auth, conversation.conversation_id, "newer")
    assert first.status_code == 200
    assert second.status_code == 200
    db.expire_all()
    older = db.get(Message, first.json()["message_id"])
    newer = db.get(Message, second.json()["message_id"])
    assert older is not None and newer is not None
    apply_message_moderation(db, newer, "allowed")
    apply_message_moderation(db, older, "allowed")
    db.commit()
    path = f"/v1/conversations/{conversation.conversation_id}/messages"
    first_page = client.get(f"{path}?limit=1", headers=bob_auth)
    assert first_page.status_code == 200
    ids = [row["message_id"] for row in first_page.json()["items"]]
    assert ids == [str(newer.message_id)]
    cursor = first_page.json()["next_cursor"]
    assert cursor
    second_page = client.get(f"{path}?limit=1&after={cursor}", headers=bob_auth)
    assert [row["message_id"] for row in second_page.json()["items"]] == [
        str(older.message_id)
    ]
    assert second_page.json()["next_cursor"] is None
    full = client.get(path, headers=bob_auth)
    assert [row["message_id"] for row in full.json()["items"]] == [
        str(newer.message_id),
        str(older.message_id),
    ]
    tamper = client.get(f"{path}?after=not-a-cursor", headers=bob_auth)
    assert tamper.status_code == 422


def test_client_message_id_replay(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    client_id = uuid4()
    first = send(client, alice_auth, conversation.conversation_id, "same", client_id)
    second = send(client, alice_auth, conversation.conversation_id, "same", client_id)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["message_id"] == second.json()["message_id"]
    conflict = send(
        client, alice_auth, conversation.conversation_id, "other", client_id
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_idempotency_key_conflict(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    headers = {**alice_auth, **key()}
    first = client.post(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        json={"client_message_id": str(uuid4()), "body": "one"},
        headers=headers,
    )
    second = client.post(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        json={"client_message_id": str(uuid4()), "body": "two"},
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_rate_limit(db: Session):
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    tight = Settings(**{**settings.model_dump(), "message_rate_per_minute": 1})
    client = TestClient(create_app(tight))
    _alice, _bob, _match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    first = send(client, alice_auth, conversation.conversation_id, "one")
    second = send(client, alice_auth, conversation.conversation_id, "two")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "rate_limited"


def test_rejected_hidden_from_recipient(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "nope")
    message_id = sent.json()["message_id"]
    db.expire_all()
    stored = db.get(Message, message_id)
    assert stored is not None
    apply_message_moderation(db, stored, "rejected")
    db.commit()
    history = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=bob_auth,
    )
    assert history.json()["items"] == []
    assert (
        client.get(
            f"/v1/conversations/{conversation.conversation_id}/messages/{message_id}",
            headers=bob_auth,
        ).status_code
        == 404
    )
    own = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages/{message_id}",
        headers=alice_auth,
    )
    assert own.json()["moderation_state"] == "rejected"
    events = list(
        db.scalars(select(OutboxEvent).where(OutboxEvent.event_name == "message"))
    )
    assert not any(
        event.payload["properties"].get("message_id") == message_id for event in events
    )
