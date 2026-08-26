from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.onboarding.helpers import key
from tests.recommendations.helpers import auth_headers, seed_pair

from ai_dating.accounts.models import Account
from ai_dating.matching.models import ConversationMember
from ai_dating.safety.lock import canonical_pair
from ai_dating.safety.models import Conversation, Match


def open_match(db: Session, alice: Account, bob: Account) -> tuple[Match, Conversation]:
    now = datetime.now(UTC)
    low, high = canonical_pair(alice.account_id, bob.account_id)
    match = Match(
        match_id=uuid4(),
        account_low_id=low,
        account_high_id=high,
        state="active",
        matched_at=now,
        ended_at=None,
        ended_by_account_id=None,
        source_like_low_id=None,
        source_like_high_id=None,
    )
    db.add(match)
    db.flush()
    conversation = Conversation(
        conversation_id=uuid4(),
        match_id=match.match_id,
        state="active",
        created_at=now,
        closed_at=None,
    )
    db.add(conversation)
    db.flush()
    for account_id in (low, high):
        db.add(
            ConversationMember(
                conversation_id=conversation.conversation_id,
                account_id=account_id,
                joined_at=now,
                last_read_message_id=None,
            )
        )
    db.commit()
    return match, conversation


def pair_with_match(db: Session):
    alice, bob = seed_pair(db)
    db.commit()
    match, conversation = open_match(db, alice[0], bob[0])
    alice_auth = auth_headers(db, alice[0].account_id)
    bob_auth = auth_headers(db, bob[0].account_id)
    return alice, bob, match, conversation, alice_auth, bob_auth


def send(
    client: TestClient,
    auth: dict,
    conversation_id: UUID,
    body: str = "hello",
    client_id: UUID | None = None,
    idem: dict | None = None,
):
    return client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={
            "client_message_id": str(client_id or uuid4()),
            "body": body,
        },
        headers={**auth, **(idem or key())},
    )
