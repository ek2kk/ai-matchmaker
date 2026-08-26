from __future__ import annotations

from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.enqueue import enqueue_event
from ai_dating.matching.models import ConversationMember, Like
from ai_dating.recommendations.models import (
    RecommendationAction,
    RecommendationBatch,
    RecommendationItem,
)
from ai_dating.safety.lock import canonical_pair, lock_pair
from ai_dating.safety.models import Conversation, Match
from ai_dating.safety.service import _end_relationship, blocked_either_way


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hidden() -> NoReturn:
    raise AppError(404, "not_found", "Not found.")


def _event(
    *,
    event_name: str,
    actor_id: UUID,
    subject_id: UUID,
    batch: RecommendationBatch,
    item: RecommendationItem,
    properties: dict,
    match_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> dict:
    return {
        "event_name": event_name,
        "schema_version": 1,
        "producer": "api",
        "owner": "matching",
        "actor_account_id": str(actor_id),
        "subject_account_id": str(subject_id),
        "recommendation_batch_id": str(batch.recommendation_batch_id),
        "recommendation_item_id": str(item.recommendation_item_id),
        "match_id": None if match_id is None else str(match_id),
        "conversation_id": None if conversation_id is None else str(conversation_id),
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": "product_pseudonymous",
        "properties": properties,
    }


def like_view(
    db: Session, action: RecommendationAction, item: RecommendationItem
) -> dict:
    match, conversation = _pair_relationship(
        db, action.actor_account_id, item.candidate_account_id
    )
    body = {
        "action_id": str(action.action_id),
        "recommendation_item_id": str(item.recommendation_item_id),
        "decision": "like",
        "match": None,
    }
    if match is not None and conversation is not None and match.state == "active":
        body["match"] = {
            "match_id": str(match.match_id),
            "conversation_id": str(conversation.conversation_id),
            "matched_at": _iso(match.matched_at),
        }
    return body


def commit_like(
    db: Session,
    account: Account,
    batch: RecommendationBatch,
    item: RecommendationItem,
    now: datetime | None = None,
) -> dict:
    now = now or _now()
    subject_id = item.candidate_account_id
    lock_pair(db, account.account_id, subject_id)
    if blocked_either_way(db, account.account_id, subject_id):
        _hidden()
    existing = db.scalar(
        select(RecommendationAction).where(
            RecommendationAction.recommendation_item_id == item.recommendation_item_id,
            RecommendationAction.actor_account_id == account.account_id,
            RecommendationAction.action.in_(("like", "pass")),
        )
    )
    if existing is not None:
        if existing.action != "like":
            raise AppError(409, "decision_conflict", "Item already has a decision.")
        return like_view(db, existing, item)
    action = RecommendationAction(
        action_id=uuid4(),
        recommendation_item_id=item.recommendation_item_id,
        actor_account_id=account.account_id,
        action="like",
        reason_code=None,
        created_at=now,
    )
    try:
        with db.begin_nested():
            db.add(action)
            db.flush()
    except IntegrityError:
        found = db.scalar(
            select(RecommendationAction).where(
                RecommendationAction.recommendation_item_id
                == item.recommendation_item_id,
                RecommendationAction.actor_account_id == account.account_id,
                RecommendationAction.action.in_(("like", "pass")),
            )
        )
        if found is None:
            _hidden()
        if found.action != "like":
            raise AppError(409, "decision_conflict", "Item already has a decision.")
        return like_view(db, found, item)
    like = db.scalar(
        select(Like).where(
            Like.actor_account_id == account.account_id,
            Like.subject_account_id == subject_id,
        )
    )
    if like is None:
        like = Like(
            like_id=uuid4(),
            actor_account_id=account.account_id,
            subject_account_id=subject_id,
            recommendation_item_id=item.recommendation_item_id,
            recommendation_action_id=action.action_id,
            state="active",
            created_at=now,
            updated_at=now,
        )
        try:
            with db.begin_nested():
                db.add(like)
                db.flush()
        except IntegrityError:
            like = db.scalar(
                select(Like).where(
                    Like.actor_account_id == account.account_id,
                    Like.subject_account_id == subject_id,
                )
            )
            if like is None:
                _hidden()
    reciprocal = db.scalar(
        select(Like).where(
            Like.actor_account_id == subject_id,
            Like.subject_account_id == account.account_id,
            Like.state == "active",
        )
    )
    match = None
    conversation = None
    created = False
    if reciprocal is not None:
        match, conversation, created = _ensure_match(
            db, account.account_id, subject_id, like, reciprocal, now
        )
    enqueue_event(
        db,
        _event(
            event_name="like",
            actor_id=account.account_id,
            subject_id=subject_id,
            batch=batch,
            item=item,
            properties={
                "action_id": str(action.action_id),
                "like_id": str(like.like_id),
                "is_reciprocal_at_commit": reciprocal is not None,
            },
            match_id=None if match is None else match.match_id,
            conversation_id=None
            if conversation is None
            else conversation.conversation_id,
        ),
    )
    if created and match is not None and conversation is not None:
        enqueue_event(
            db,
            _event(
                event_name="match",
                actor_id=account.account_id,
                subject_id=subject_id,
                batch=batch,
                item=item,
                properties={"source": "reciprocal_like"},
                match_id=match.match_id,
                conversation_id=conversation.conversation_id,
            ),
        )
    return like_view(db, action, item)


def _pair_relationship(
    db: Session, left: UUID, right: UUID
) -> tuple[Match | None, Conversation | None]:
    low, high = canonical_pair(left, right)
    match = db.scalar(
        select(Match).where(
            Match.account_low_id == low,
            Match.account_high_id == high,
        )
    )
    if match is None:
        return None, None
    conversation = db.scalar(
        select(Conversation).where(Conversation.match_id == match.match_id)
    )
    return match, conversation


def _ensure_match(
    db: Session,
    actor_id: UUID,
    subject_id: UUID,
    this_like: Like,
    other_like: Like,
    now: datetime,
) -> tuple[Match | None, Conversation | None, bool]:
    low, high = canonical_pair(actor_id, subject_id)
    source_low = this_like if this_like.actor_account_id == low else other_like
    source_high = other_like if source_low is this_like else this_like
    match_id = uuid4()
    inserted = db.execute(
        insert(Match)
        .values(
            match_id=match_id,
            account_low_id=low,
            account_high_id=high,
            state="active",
            matched_at=now,
            ended_at=None,
            ended_by_account_id=None,
            source_like_low_id=source_low.like_id,
            source_like_high_id=source_high.like_id,
        )
        .on_conflict_do_nothing(index_elements=["account_low_id", "account_high_id"])
        .returning(Match.match_id)
    ).scalar()
    if inserted is None:
        match, conversation = _pair_relationship(db, actor_id, subject_id)
        return match, conversation, False
    match = db.get(Match, inserted)
    assert match is not None
    conversation = Conversation(
        conversation_id=uuid4(),
        match_id=match.match_id,
        state="active",
        created_at=now,
        closed_at=None,
    )
    db.add(conversation)
    db.flush()
    db.add(
        ConversationMember(
            conversation_id=conversation.conversation_id,
            account_id=low,
            joined_at=now,
            last_read_message_id=None,
        )
    )
    db.add(
        ConversationMember(
            conversation_id=conversation.conversation_id,
            account_id=high,
            joined_at=now,
            last_read_message_id=None,
        )
    )
    db.flush()
    return match, conversation, True


def unmatch(db: Session, account: Account, match_id: UUID) -> None:
    match = db.scalar(
        select(Match).where(
            Match.match_id == match_id,
            or_(
                Match.account_low_id == account.account_id,
                Match.account_high_id == account.account_id,
            ),
        )
    )
    if match is None:
        _hidden()
    subject_id = (
        match.account_high_id
        if match.account_low_id == account.account_id
        else match.account_low_id
    )
    lock_pair(db, account.account_id, subject_id)
    db.refresh(match)
    if match.state == "unmatched":
        return
    if match.state != "active":
        _hidden()
    now = _now()
    ended, conversation = _end_relationship(
        db, account.account_id, subject_id, now, end_state="unmatched"
    )
    if ended is None:
        return
    age = max(0, int((now - ended.matched_at).total_seconds()))
    enqueue_event(
        db,
        {
            "event_name": "unmatch",
            "schema_version": 1,
            "producer": "api",
            "owner": "matching",
            "actor_account_id": str(account.account_id),
            "subject_account_id": str(subject_id),
            "recommendation_batch_id": None,
            "recommendation_item_id": None,
            "match_id": str(ended.match_id),
            "conversation_id": None
            if conversation is None
            else str(conversation.conversation_id),
            "request_id": request_id_of() or "local",
            "experiment_assignments": {},
            "privacy_classification": "product_pseudonymous",
            "properties": {
                "initiator_role": "self",
                "match_age_seconds": age,
            },
        },
    )
