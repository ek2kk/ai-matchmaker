from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.ai.helpers import drain_jobs
from tests.messaging.helpers import pair_with_match, send
from tests.onboarding.helpers import key

from ai_dating.events.models import OutboxEvent

pytestmark = [pytest.mark.postgres]


def _events(db: Session, name: str, message_id: str) -> list[OutboxEvent]:
    return [
        row
        for row in db.scalars(select(OutboxEvent).where(OutboxEvent.event_name == name))
        if row.payload.get("properties", {}).get("message_id") == message_id
    ]


def test_allow_emits_message_without_body(client: TestClient, db: Session):
    _alice, _bob, match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "first body")
    drain_jobs()
    message_id = sent.json()["message_id"]
    db.expire_all()
    rows = _events(db, "message", message_id)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["owner"] == "messaging"
    assert payload["match_id"] == str(match.match_id)
    assert payload["conversation_id"] == str(conversation.conversation_id)
    assert payload["properties"]["sequence_kind"] == "first"
    assert payload["properties"]["moderation_state"] == "allowed"
    assert "body" not in payload["properties"]
    assert "first body" not in str(payload)


def test_reply_uses_other_member_allowed_message(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    first = send(client, alice_auth, conversation.conversation_id, "hey")
    drain_jobs()
    reply = send(client, bob_auth, conversation.conversation_id, "hi back")
    drain_jobs()
    db.expire_all()
    first_id = first.json()["message_id"]
    reply_id = reply.json()["message_id"]
    message_events = _events(db, "message", reply_id)
    assert len(message_events) == 1
    assert message_events[0].payload["properties"]["sequence_kind"] == "followup"
    replies = _events(db, "reply", reply_id)
    assert len(replies) == 1
    props = replies[0].payload["properties"]
    assert props["reply_to_message_id"] == first_id
    assert props["latency_seconds"] >= 0
    assert "body" not in props
    assert "hi back" not in str(replies[0].payload)


def test_report_allowed_message(client: TestClient, db: Session):
    alice, bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, bob_auth, conversation.conversation_id, "spam")
    drain_jobs()
    unknown = client.post(
        "/v1/reports",
        json={
            "profile_id": str(bob[1].profile_id),
            "message_id": str(uuid4()),
            "reason_code": "spam",
        },
        headers={**alice_auth, **key()},
    )
    assert unknown.status_code == 404
    ok = client.post(
        "/v1/reports",
        json={
            "profile_id": str(bob[1].profile_id),
            "message_id": sent.json()["message_id"],
            "reason_code": "spam",
        },
        headers={**alice_auth, **key()},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "received"
    del alice
