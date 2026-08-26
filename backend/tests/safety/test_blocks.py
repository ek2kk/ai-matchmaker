from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.onboarding.helpers import account, auth_of, key, profile_body
from tests.recommendations.helpers import seed_exposure, seed_person

from ai_dating.accounts.models import Account
from ai_dating.config import load_settings
from ai_dating.database.engine import create_sync_engine
from ai_dating.errors import AppError
from ai_dating.events.audit import SecurityAuditLog
from ai_dating.events.models import OutboxEvent
from ai_dating.profiles.public import get_public_profile
from ai_dating.recommendations.models import RecommendationBatch
from ai_dating.safety.lock import canonical_pair
from ai_dating.safety.models import Block, Conversation, Match
from ai_dating.safety.service import create_block

pytestmark = [pytest.mark.postgres]
_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def _engine():
    settings = load_settings()
    if not (settings.database_url or settings.database_direct_url):
        pytest.skip("DATABASE_DIRECT_URL is not set")
    return create_sync_engine(settings)


def _profile_id(client: TestClient, auth: dict) -> str:
    patched = client.patch("/v1/onboarding/profile", json=profile_body(0), headers=auth)
    assert patched.status_code == 200, patched.text
    profile_id = patched.json()["profile_id"]
    assert profile_id
    return profile_id


def test_block_list_unblock_and_idor(client: TestClient):
    alice = account(client)
    bob = account(client)
    alice_auth = auth_of(alice)
    bob_auth = auth_of(bob)
    bob_profile = _profile_id(client, bob_auth)
    created = client.post(
        "/v1/blocks",
        json={"profile_id": bob_profile, "reason_code": "spam"},
        headers={**alice_auth, **key()},
    )
    assert created.status_code == 204
    listed = client.get("/v1/blocks", headers=alice_auth)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["profile_id"] == bob_profile
    assert "reason_code" not in items[0]
    block_id = items[0]["block_id"]
    assert client.get("/v1/blocks", headers=bob_auth).json()["items"] == []
    stolen = client.delete(
        f"/v1/blocks/{block_id}",
        headers={**bob_auth, **key()},
    )
    assert stolen.status_code == 404
    ended = client.delete(
        f"/v1/blocks/{block_id}",
        headers={**alice_auth, **key()},
    )
    assert ended.status_code == 204
    assert client.get("/v1/blocks", headers=alice_auth).json()["items"] == []


def test_block_idempotent_and_unknown_is_404(client: TestClient):
    alice = account(client)
    bob = account(client)
    auth = auth_of(alice)
    bob_profile = _profile_id(client, auth_of(bob))
    payload = {"profile_id": bob_profile, "reason_code": "other"}
    header = {**auth, **key()}
    assert client.post("/v1/blocks", json=payload, headers=header).status_code == 204
    assert client.post("/v1/blocks", json=payload, headers=header).status_code == 204
    again = client.post(
        "/v1/blocks",
        json=payload,
        headers={**auth, **key()},
    )
    assert again.status_code == 204
    assert (
        client.post(
            "/v1/blocks",
            json={"profile_id": str(uuid4())},
            headers={**auth, **key()},
        ).status_code
        == 404
    )
    self_id = _profile_id(client, auth)
    assert (
        client.post(
            "/v1/blocks",
            json={"profile_id": self_id},
            headers={**auth, **key()},
        ).status_code
        == 404
    )
    both = client.post(
        "/v1/blocks",
        json={"profile_id": bob_profile, "match_id": str(uuid4())},
        headers={**auth, **key()},
    )
    assert both.status_code == 422


def test_no_staff_case_http(client: TestClient):
    alice = account(client)
    auth = auth_of(alice)
    assert client.get("/v1/moderation-cases", headers=auth).status_code == 404
    assert client.get("/v1/reports", headers=auth).status_code == 405


def test_report_creates_block_case_and_audit(client: TestClient):
    alice = account(client)
    bob = account(client)
    alice_auth = auth_of(alice)
    bob_profile = _profile_id(client, auth_of(bob))
    details = "secret report text that must not leak"
    response = client.post(
        "/v1/reports",
        json={
            "profile_id": bob_profile,
            "reason_code": "harassment",
            "details": details,
        },
        headers={**alice_auth, **key()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert "details" not in body
    listed = client.get("/v1/blocks", headers=alice_auth).json()["items"]
    assert listed[0]["profile_id"] == bob_profile
    engine = _engine()
    with Session(engine) as session:
        events = list(
            session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_name.in_(("block", "report"))
                )
            )
        )
        names = {
            row.event_name
            for row in events
            if row.payload.get("actor_account_id") == alice["account_id"]
        }
        assert names == {"block", "report"}
        report_event = next(
            row
            for row in events
            if row.event_name == "report"
            and row.payload.get("actor_account_id") == alice["account_id"]
        )
        assert report_event.payload["privacy_classification"] == "security_restricted"
        assert details not in str(report_event.payload)
        audits = list(session.scalars(select(SecurityAuditLog)))
        report_audits = [
            row
            for row in audits
            if row.action == "report.create"
            and str(row.actor_id) == alice["account_id"]
        ]
        assert report_audits
        assert details not in str(report_audits[-1].metadata_json)


def test_report_unknown_message_is_404(client: TestClient):
    alice = account(client)
    bob = account(client)
    response = client.post(
        "/v1/reports",
        json={
            "profile_id": _profile_id(client, auth_of(bob)),
            "message_id": str(uuid4()),
            "reason_code": "spam",
        },
        headers={**auth_of(alice), **key()},
    )
    assert response.status_code == 404


def test_block_hides_both_directions():
    engine = _engine()
    with Session(engine) as session:
        alice, alice_profile, _ = seed_person(session, gender="woman")
        bob, bob_profile, _ = seed_person(session, gender="man", accepted=["woman"])
        session.commit()
        create_block(
            session,
            alice,
            profile_id=bob_profile.profile_id,
            match_id=None,
            reason_code="other",
        )
        session.commit()
        try:
            get_public_profile(session, alice.account_id, bob_profile.profile_id)
            raise AssertionError("expected 404")
        except AppError as exc:
            assert exc.status == 404
        try:
            get_public_profile(session, bob.account_id, alice_profile.profile_id)
            raise AssertionError("expected 404")
        except AppError as exc:
            assert exc.status == 404


def test_block_ends_match_and_expires_batch():
    engine = _engine()
    with Session(engine) as session:
        alice, _alice_profile, _ = seed_person(session, gender="woman")
        bob, bob_profile, _ = seed_person(session, gender="man", accepted=["woman"])
        now = _NOW
        low, high = canonical_pair(alice.account_id, bob.account_id)
        match = Match(
            match_id=uuid4(),
            account_low_id=low,
            account_high_id=high,
            state="active",
            matched_at=now,
            ended_at=None,
            ended_by_account_id=None,
        )
        session.add(match)
        session.flush()
        conversation = Conversation(
            conversation_id=uuid4(),
            match_id=match.match_id,
            state="active",
            created_at=now,
            closed_at=None,
        )
        session.add(conversation)
        seed_exposure(session, alice.account_id, bob.account_id)
        session.flush()
        create_block(
            session,
            alice,
            profile_id=bob_profile.profile_id,
            match_id=None,
            reason_code="spam",
        )
        session.commit()
        session.refresh(match)
        session.refresh(conversation)
        assert match.state == "blocked"
        assert match.ended_at is not None
        assert conversation.state == "closed"
        batch = session.scalar(
            select(RecommendationBatch).where(
                RecommendationBatch.owner_account_id == alice.account_id
            )
        )
        assert batch is not None
        assert batch.status == "expired"


def test_concurrent_blocks_one_row():
    engine = _engine()
    with Session(engine) as session:
        alice, _alice_profile, _ = seed_person(session, gender="woman")
        bob, bob_profile, _ = seed_person(session, gender="man", accepted=["woman"])
        session.commit()
        alice_id = alice.account_id
        bob_pid = bob_profile.profile_id

    def worker() -> None:
        with Session(engine) as session:
            actor = session.get(Account, alice_id)
            assert actor is not None
            create_block(
                session,
                actor,
                profile_id=bob_pid,
                match_id=None,
                reason_code="other",
            )
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _n: worker(), range(2)))
    with Session(engine) as session:
        count = session.scalar(
            select(func.count())
            .select_from(Block)
            .where(
                Block.blocker_account_id == alice_id,
                Block.ended_at.is_(None),
            )
        )
        assert count == 1
