from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.ai.helpers import drain_jobs
from tests.messaging.helpers import pair_with_match, send
from tests.onboarding.helpers import key
from tests.recommendations.helpers import auth_headers, seed_person

from ai_dating.safety.models import Conversation, Match

pytestmark = [pytest.mark.postgres]


def test_non_member_cannot_read(client: TestClient, db: Session):
    _alice, _bob, _match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    outsider, _profile, _prefs = seed_person(db, gender="woman")
    db.commit()
    other = auth_headers(db, outsider.account_id)
    listed = client.get(
        f"/v1/conversations/{conversation.conversation_id}/messages",
        headers=other,
    )
    assert listed.status_code == 404
    posted = send(client, other, conversation.conversation_id)
    assert posted.status_code == 404
    assert client.get("/v1/matches", headers=alice_auth).status_code == 200


def test_block_hides_messages(client: TestClient, db: Session):
    alice, bob, _match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id, "hi")
    assert sent.status_code == 200
    drain_jobs()
    blocked = client.post(
        "/v1/blocks",
        json={"profile_id": str(bob[1].profile_id)},
        headers={**alice_auth, **key()},
    )
    assert blocked.status_code == 204
    del alice
    assert (
        client.get(
            f"/v1/conversations/{conversation.conversation_id}/messages",
            headers=bob_auth,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/conversations/{conversation.conversation_id}/messages",
            headers=alice_auth,
        ).status_code
        == 404
    )


def test_unmatch_closes_messages(client: TestClient, db: Session):
    _alice, _bob, match, conversation, alice_auth, bob_auth = pair_with_match(db)
    sent = send(client, alice_auth, conversation.conversation_id)
    assert sent.status_code == 200
    drain_jobs()
    closed = client.post(
        f"/v1/matches/{match.match_id}/unmatch",
        headers={**alice_auth, **key()},
    )
    assert closed.status_code == 204
    replay = client.post(
        f"/v1/matches/{match.match_id}/unmatch",
        headers={**alice_auth, **key()},
    )
    assert replay.status_code == 204
    assert send(client, bob_auth, conversation.conversation_id).status_code == 404
    assert (
        client.get(
            f"/v1/conversations/{conversation.conversation_id}/messages",
            headers=alice_auth,
        ).status_code
        == 404
    )


def test_unknown_conversation_is_404(client: TestClient, db: Session):
    _alice, _bob, _match, _conversation, alice_auth, _bob_auth = pair_with_match(db)
    assert (
        client.get(
            f"/v1/conversations/{uuid4()}/messages",
            headers=alice_auth,
        ).status_code
        == 404
    )


def test_list_matches_and_conversations(client: TestClient, db: Session):
    _alice, _bob, match, conversation, alice_auth, _bob_auth = pair_with_match(db)
    matches = client.get("/v1/matches", headers=alice_auth)
    assert matches.status_code == 200
    items = matches.json()["items"]
    assert len(items) == 1
    assert items[0]["match_id"] == str(match.match_id)
    assert items[0]["conversation_id"] == str(conversation.conversation_id)
    assert "counterpart" in items[0]
    convs = client.get("/v1/conversations", headers=alice_auth)
    assert convs.status_code == 200
    assert convs.json()["items"][0]["conversation_id"] == str(
        conversation.conversation_id
    )


def test_unmatch_idempotent_key(client: TestClient, db: Session):
    _alice, _bob, match, _conversation, alice_auth, _bob_auth = pair_with_match(db)
    headers = {**alice_auth, **key()}
    first = client.post(f"/v1/matches/{match.match_id}/unmatch", headers=headers)
    second = client.post(f"/v1/matches/{match.match_id}/unmatch", headers=headers)
    assert first.status_code == 204
    assert second.status_code == 204
    db.expire_all()
    loaded = db.get(Match, match.match_id)
    assert loaded is not None
    assert loaded.state == "unmatched"
    conv = db.scalar(
        select(Conversation).where(Conversation.match_id == match.match_id)
    )
    assert conv is not None
    assert conv.state == "closed"
