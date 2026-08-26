import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.ai.helpers import drain_jobs
from tests.messaging.helpers import pair_with_match, send

from ai_dating.messaging.models import Message
from ai_dating.messaging.service import apply_message_moderation

pytestmark = [pytest.mark.postgres]


def test_worker_auto_approves_held_message(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "ok")
    assert sent.json()["moderation_state"] == "held"
    drain_jobs()
    listed = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=bob_auth,
    )
    assert listed.json()["items"][0]["moderation_state"] == "allowed"


def test_reject_does_not_surface_to_recipient(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "bad")
    db.expire_all()
    stored = db.get(Message, sent.json()["message_id"])
    assert stored is not None
    assert apply_message_moderation(db, stored, "rejected")
    db.commit()
    listed = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=bob_auth,
    )
    assert listed.json()["items"] == []
