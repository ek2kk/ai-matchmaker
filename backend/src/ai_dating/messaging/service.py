from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.ai.models import AiOperation
from ai_dating.config import Settings
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.jobs.enqueue import enqueue_job
from ai_dating.matching.models import ConversationMember
from ai_dating.messaging.constants import (
    JOB_TYPE_MODERATE_MESSAGE,
    MESSAGE_BODY_MAX,
    REPLY_WINDOW_DAYS,
)
from ai_dating.messaging.cursors import decode_cursor, encode_cursor
from ai_dating.messaging.models import Message
from ai_dating.profiles.models import Profile
from ai_dating.profiles.public import public_card
from ai_dating.safety.models import Conversation, Match
from ai_dating.safety.service import blocked_either_way

_DENIED = frozenset({"suspended", "deleted", "deletion_pending"})
_MATCH_PAGE = 20
_CONV_PAGE = 20
_MSG_PAGE = 50


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _hidden() -> NoReturn:
    raise AppError(404, "not_found", "Not found.")


def _account_ok(account: Account | None) -> bool:
    return (
        account is not None
        and account.deleted_at is None
        and account.status not in _DENIED
    )


def counterpart_id(match: Match, actor_id: UUID) -> UUID:
    if actor_id == match.account_low_id:
        return match.account_high_id
    if actor_id == match.account_high_id:
        return match.account_low_id
    _hidden()


def counterpart_card(db: Session, account_id: UUID) -> dict:
    row = db.execute(
        select(Account, Profile)
        .join(Profile, Profile.account_id == Account.account_id)
        .where(
            Account.account_id == account_id,
            Account.deleted_at.is_(None),
            Profile.deleted_at.is_(None),
        )
    ).first()
    if row is None:
        _hidden()
    account, profile = row
    if account.date_of_birth is None:
        _hidden()
    return public_card(account, profile)


def _member(
    db: Session, conversation_id: UUID, account_id: UUID
) -> ConversationMember | None:
    return db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.account_id == account_id,
        )
    )


def load_active_conversation(
    db: Session, actor: Account, conversation_id: UUID
) -> tuple[Conversation, Match, UUID]:
    if not _account_ok(actor):
        _hidden()
    member = _member(db, conversation_id, actor.account_id)
    if member is None:
        _hidden()
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.state == "active",
        )
    )
    if conversation is None:
        _hidden()
    match = db.scalar(
        select(Match).where(
            Match.match_id == conversation.match_id,
            Match.state == "active",
        )
    )
    if match is None:
        _hidden()
    other_id = counterpart_id(match, actor.account_id)
    other = db.get(Account, other_id)
    if not _account_ok(other):
        _hidden()
    if blocked_either_way(db, actor.account_id, other_id):
        _hidden()
    return conversation, match, other_id


def message_view(row: Message, *, include_body: bool) -> dict:
    body = row.body if include_body else None
    return {
        "message_id": str(row.message_id),
        "conversation_id": str(row.conversation_id),
        "sender_account_id": str(row.sender_account_id),
        "client_message_id": str(row.client_message_id),
        "body": body,
        "moderation_state": row.moderation_state,
        "created_at": _iso(row.created_at),
        "allowed_at": None if row.allowed_at is None else _iso(row.allowed_at),
    }


def list_matches(
    db: Session, actor: Account, *, state: str, limit: int, after: str | None
) -> dict:
    if state != "active":
        raise AppError(422, "validation_error", "Invalid request.")
    if not _account_ok(actor):
        _hidden()
    bound = min(max(limit, 1), _MATCH_PAGE)
    stmt = (
        select(Match, Conversation)
        .join(Conversation, Conversation.match_id == Match.match_id)
        .where(
            Match.state == "active",
            Conversation.state == "active",
            or_(
                Match.account_low_id == actor.account_id,
                Match.account_high_id == actor.account_id,
            ),
        )
        .order_by(Match.matched_at.desc(), Match.match_id.desc())
    )
    if after:
        ts, marker = decode_cursor(after)
        stmt = stmt.where(
            (Match.matched_at < ts)
            | ((Match.matched_at == ts) & (Match.match_id < marker))
        )
    rows = list(db.execute(stmt.limit(bound + 1)).all())
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        last_match = rows[-1][0]
        next_cursor = encode_cursor(last_match.matched_at, last_match.match_id)
    items = []
    for match, conversation in rows:
        other = counterpart_id(match, actor.account_id)
        if blocked_either_way(db, actor.account_id, other):
            continue
        items.append(
            {
                "match_id": str(match.match_id),
                "conversation_id": str(conversation.conversation_id),
                "matched_at": _iso(match.matched_at),
                "counterpart": counterpart_card(db, other),
            }
        )
    return {"items": items, "next_cursor": next_cursor}


def list_conversations(
    db: Session, actor: Account, *, limit: int, after: str | None
) -> dict:
    if not _account_ok(actor):
        _hidden()
    bound = min(max(limit, 1), _CONV_PAGE)
    last_allowed = (
        select(func.max(Message.allowed_at))
        .where(
            Message.conversation_id == Conversation.conversation_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    activity = func.coalesce(last_allowed, Conversation.created_at)
    stmt = (
        select(Conversation, Match, activity.label("last_activity_at"))
        .join(Match, Match.match_id == Conversation.match_id)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Conversation.conversation_id,
        )
        .where(
            ConversationMember.account_id == actor.account_id,
            Conversation.state == "active",
            Match.state == "active",
        )
        .order_by(activity.desc(), Conversation.conversation_id.desc())
    )
    if after:
        ts, marker = decode_cursor(after)
        stmt = stmt.where(
            (activity < ts)
            | ((activity == ts) & (Conversation.conversation_id < marker))
        )
    rows = list(db.execute(stmt.limit(bound + 1)).all())
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        last = rows[-1]
        next_cursor = encode_cursor(last.last_activity_at, last[0].conversation_id)
    items = []
    for conversation, match, last_activity_at in rows:
        other = counterpart_id(match, actor.account_id)
        if blocked_either_way(db, actor.account_id, other):
            continue
        items.append(
            {
                "conversation_id": str(conversation.conversation_id),
                "match_id": str(match.match_id),
                "last_activity_at": _iso(last_activity_at),
                "counterpart": counterpart_card(db, other),
            }
        )
    return {"items": items, "next_cursor": next_cursor}


def list_messages(
    db: Session,
    actor: Account,
    conversation_id: UUID,
    *,
    limit: int,
    after: str | None,
) -> dict:
    load_active_conversation(db, actor, conversation_id)
    bound = min(max(limit, 1), _MSG_PAGE)
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
        )
        .order_by(Message.allowed_at.asc(), Message.message_id.asc())
    )
    if after:
        ts, marker = decode_cursor(after)
        stmt = stmt.where(
            (Message.allowed_at > ts)
            | ((Message.allowed_at == ts) & (Message.message_id > marker))
        )
    rows = list(db.scalars(stmt.limit(bound + 1)).all())
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        last = rows[-1]
        assert last.allowed_at is not None
        next_cursor = encode_cursor(last.allowed_at, last.message_id)
    return {
        "items": [message_view(row, include_body=True) for row in rows],
        "next_cursor": next_cursor,
    }


def get_message(
    db: Session, actor: Account, conversation_id: UUID, message_id: UUID
) -> dict:
    load_active_conversation(db, actor, conversation_id)
    row = db.scalar(
        select(Message).where(
            Message.message_id == message_id,
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
    )
    if row is None:
        _hidden()
    if row.moderation_state == "allowed":
        return message_view(row, include_body=True)
    if row.sender_account_id == actor.account_id:
        return message_view(row, include_body=True)
    _hidden()


def send_message(
    db: Session,
    settings: Settings,
    actor: Account,
    conversation_id: UUID,
    *,
    client_message_id: UUID,
    body: str,
) -> dict:
    load_active_conversation(db, actor, conversation_id)
    text = body.strip()
    if not text or len(text) > MESSAGE_BODY_MAX:
        raise AppError(422, "validation_error", "Invalid request.")
    existing = db.scalar(
        select(Message).where(
            Message.sender_account_id == actor.account_id,
            Message.client_message_id == client_message_id,
        )
    )
    if existing is not None:
        if existing.body != text or existing.conversation_id != conversation_id:
            raise AppError(409, "idempotency_conflict", "Idempotency key reused.")
        return message_view(existing, include_body=True)
    now = _now()
    minute = now - timedelta(minutes=1)
    day = now - timedelta(days=1)
    per_min = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.sender_account_id == actor.account_id,
            Message.created_at >= minute,
        )
    )
    per_day = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.sender_account_id == actor.account_id,
            Message.created_at >= day,
        )
    )
    if int(per_min or 0) >= settings.message_rate_per_minute:
        raise AppError(429, "rate_limited", "Try again later.")
    if int(per_day or 0) >= settings.message_rate_per_day:
        raise AppError(429, "rate_limited", "Try again later.")
    row = Message(
        message_id=uuid4(),
        conversation_id=conversation_id,
        sender_account_id=actor.account_id,
        client_message_id=client_message_id,
        body=text,
        moderation_state="held",
        created_at=now,
        allowed_at=None,
        deleted_at=None,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        found = db.scalar(
            select(Message).where(
                Message.sender_account_id == actor.account_id,
                Message.client_message_id == client_message_id,
            )
        )
        if found is None:
            _hidden()
        if found.body != text or found.conversation_id != conversation_id:
            raise AppError(409, "idempotency_conflict", "Idempotency key reused.")
        return message_view(found, include_body=True)
    enqueue_job(
        db,
        job_type=JOB_TYPE_MODERATE_MESSAGE,
        dedup_key=f"{JOB_TYPE_MODERATE_MESSAGE}:{row.message_id}",
        payload={"message_id": str(row.message_id)},
        now=now,
        max_attempts=3,
    )
    return message_view(row, include_body=True)


def mark_read(
    db: Session, actor: Account, conversation_id: UUID, last_read_message_id: UUID
) -> None:
    load_active_conversation(db, actor, conversation_id)
    message = db.scalar(
        select(Message).where(
            Message.message_id == last_read_message_id,
            Message.conversation_id == conversation_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
        )
    )
    if message is None:
        _hidden()
    member = _member(db, conversation_id, actor.account_id)
    if member is None:
        _hidden()
    member.last_read_message_id = last_read_message_id


def apply_message_moderation(
    db: Session,
    message: Message,
    decision: str,
    *,
    job_id: UUID | None = None,
) -> bool:
    if decision not in {"allowed", "rejected"}:
        raise ValueError("decision")
    now = _now()
    values: dict = {"moderation_state": decision}
    if decision == "allowed":
        values["allowed_at"] = now
    result = db.execute(
        update(Message)
        .where(
            Message.message_id == message.message_id,
            Message.moderation_state == "held",
            Message.deleted_at.is_(None),
        )
        .values(**values)
        .returning(Message.message_id)
    ).first()
    if result is None:
        return False
    db.refresh(message)
    db.add(
        AiOperation(
            ai_operation_id=uuid4(),
            job_id=job_id,
            operation_type="moderation",
            prompt_version="message-moderation-v1",
            model_version="local-auto",
            source_entity_type="message",
            source_entity_id=message.message_id,
            source_version=1,
            latency_ms=None,
            token_input=None,
            token_output=None,
            result_status="succeeded",
            safety_result="passed" if decision == "allowed" else "rejected",
            created_at=now,
        )
    )
    if decision == "allowed":
        _enqueue_allow_events(db, message)
    return True


def _enqueue_allow_events(db: Session, message: Message) -> None:
    conversation = db.get(Conversation, message.conversation_id)
    if conversation is None:
        return
    match = db.get(Match, conversation.match_id)
    if match is None:
        return
    other_id = counterpart_id(match, message.sender_account_id)
    allowed = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
        )
    )
    sequence_kind = "first" if int(allowed or 0) == 1 else "followup"
    base = {
        "schema_version": 1,
        "producer": "worker",
        "owner": "messaging",
        "actor_account_id": str(message.sender_account_id),
        "subject_account_id": str(other_id),
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": str(match.match_id),
        "conversation_id": str(conversation.conversation_id),
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
    }
    enqueue_event(
        db,
        {
            **base,
            "event_name": "message",
            "properties": {
                "message_id": str(message.message_id),
                "sequence_kind": sequence_kind,
                "moderation_state": "allowed",
            },
        },
    )
    prior = db.scalar(
        select(Message)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.sender_account_id != message.sender_account_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
            Message.message_id != message.message_id,
        )
        .order_by(Message.allowed_at.desc(), Message.message_id.desc())
        .limit(1)
    )
    if prior is None or prior.allowed_at is None or message.allowed_at is None:
        return
    delta = message.allowed_at - prior.allowed_at
    if delta > timedelta(days=REPLY_WINDOW_DAYS):
        return
    enqueue_event(
        db,
        {
            **base,
            "event_name": "reply",
            "properties": {
                "message_id": str(message.message_id),
                "reply_to_message_id": str(prior.message_id),
                "latency_seconds": max(0, int(delta.total_seconds())),
            },
        },
    )


def reportable_message(
    db: Session, actor_id: UUID, subject_id: UUID, message_id: UUID
) -> Message:
    row = db.scalar(
        select(Message)
        .join(
            ConversationMember,
            ConversationMember.conversation_id == Message.conversation_id,
        )
        .where(
            Message.message_id == message_id,
            Message.moderation_state == "allowed",
            Message.deleted_at.is_(None),
            ConversationMember.account_id == actor_id,
        )
    )
    if row is None:
        _hidden()
    members = set(
        db.scalars(
            select(ConversationMember.account_id).where(
                ConversationMember.conversation_id == row.conversation_id
            )
        )
    )
    if subject_id not in members or actor_id not in members:
        _hidden()
    return row
