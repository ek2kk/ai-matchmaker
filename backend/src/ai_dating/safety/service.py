from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_dating.accounts.models import Account
from ai_dating.errors import AppError, request_id_of
from ai_dating.events.audit import write_audit
from ai_dating.events.enqueue import enqueue_event
from ai_dating.profiles.models import Profile
from ai_dating.recommendations.models import RecommendationBatch, RecommendationItem
from ai_dating.safety.constants import DEFAULT_REASON, REASON_CODES, SEVERITY
from ai_dating.safety.lock import canonical_pair, lock_pair
from ai_dating.safety.models import Block, Conversation, Match, ModerationCase, Report

_PAGE = 50


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def blocked_either_way(db: Session, left: UUID, right: UUID) -> bool:
    return (
        db.scalar(
            select(Block.block_id).where(
                Block.ended_at.is_(None),
                or_(
                    (Block.blocker_account_id == left)
                    & (Block.blocked_account_id == right),
                    (Block.blocker_account_id == right)
                    & (Block.blocked_account_id == left),
                ),
            )
        )
        is not None
    )


def _reason(code: str | None) -> str:
    value = (code or DEFAULT_REASON).strip()
    if value not in REASON_CODES:
        raise AppError(422, "validation_error", "Invalid request.")
    return value


def _subject_profile(db: Session, profile_id: UUID, actor_id: UUID) -> Profile:
    profile = db.scalar(
        select(Profile).where(
            Profile.profile_id == profile_id,
            Profile.deleted_at.is_(None),
        )
    )
    if profile is None or profile.account_id == actor_id:
        raise AppError(404, "not_found", "Not found.")
    account = db.get(Account, profile.account_id)
    if account is None or account.deleted_at is not None:
        raise AppError(404, "not_found", "Not found.")
    return profile


def _subject_from_match(db: Session, match_id: UUID, actor_id: UUID) -> UUID:
    match = db.get(Match, match_id)
    if match is None:
        raise AppError(404, "not_found", "Not found.")
    if actor_id == match.account_low_id:
        return match.account_high_id
    if actor_id == match.account_high_id:
        return match.account_low_id
    raise AppError(404, "not_found", "Not found.")


def _expire_direction(db: Session, owner_id: UUID, candidate_id: UUID) -> None:
    item_ids = select(RecommendationItem.recommendation_batch_id).where(
        RecommendationItem.candidate_account_id == candidate_id
    )
    db.execute(
        update(RecommendationBatch)
        .where(
            RecommendationBatch.owner_account_id == owner_id,
            RecommendationBatch.status.in_(("building", "ready", "served")),
            RecommendationBatch.recommendation_batch_id.in_(item_ids),
        )
        .values(status="expired")
    )


def expire_pair_batches(db: Session, left: UUID, right: UUID) -> None:
    _expire_direction(db, left, right)
    _expire_direction(db, right, left)


def _end_relationship(
    db: Session,
    actor_id: UUID,
    subject_id: UUID,
    now: datetime,
    *,
    end_state: str = "blocked",
) -> tuple[Match | None, Conversation | None]:
    low, high = canonical_pair(actor_id, subject_id)
    match = db.scalar(
        select(Match).where(
            Match.account_low_id == low,
            Match.account_high_id == high,
            Match.state == "active",
        )
    )
    if match is None:
        return None, None
    match.state = end_state
    match.ended_at = now
    match.ended_by_account_id = actor_id
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.match_id == match.match_id,
            Conversation.state == "active",
        )
    )
    if conversation is not None:
        conversation.state = "closed"
        conversation.closed_at = now
    return match, conversation


def _event_base(
    *,
    event_name: str,
    actor_id: UUID,
    subject_id: UUID,
    match: Match | None,
    conversation: Conversation | None,
    classification: str,
    properties: dict,
) -> dict:
    return {
        "event_name": event_name,
        "schema_version": 1,
        "producer": "api",
        "owner": "safety",
        "actor_account_id": str(actor_id),
        "subject_account_id": str(subject_id),
        "recommendation_batch_id": None,
        "recommendation_item_id": None,
        "match_id": None if match is None else str(match.match_id),
        "conversation_id": None
        if conversation is None
        else str(conversation.conversation_id),
        "request_id": request_id_of() or "local",
        "experiment_assignments": {},
        "privacy_classification": classification,
        "properties": properties,
    }


def create_block(
    db: Session,
    actor: Account,
    *,
    profile_id: UUID | None,
    match_id: UUID | None,
    reason_code: str | None,
) -> Block:
    if profile_id is not None:
        subject_id = _subject_profile(db, profile_id, actor.account_id).account_id
    elif match_id is not None:
        subject_id = _subject_from_match(db, match_id, actor.account_id)
    else:
        raise AppError(422, "validation_error", "Invalid request.")
    reason = _reason(reason_code)
    lock_pair(db, actor.account_id, subject_id)
    existing = db.scalar(
        select(Block).where(
            Block.blocker_account_id == actor.account_id,
            Block.blocked_account_id == subject_id,
            Block.ended_at.is_(None),
        )
    )
    if existing is not None:
        return existing
    now = _now()
    block_id = uuid4()
    inserted = db.execute(
        insert(Block)
        .values(
            block_id=block_id,
            blocker_account_id=actor.account_id,
            blocked_account_id=subject_id,
            reason_code=reason,
            created_at=now,
            ended_at=None,
        )
        .on_conflict_do_nothing(
            index_elements=["blocker_account_id", "blocked_account_id"],
            index_where=Block.ended_at.is_(None),
        )
        .returning(Block.block_id)
    ).scalar()
    if inserted is None:
        found = db.scalar(
            select(Block).where(
                Block.blocker_account_id == actor.account_id,
                Block.blocked_account_id == subject_id,
                Block.ended_at.is_(None),
            )
        )
        if found is None:
            raise AppError(404, "not_found", "Not found.")
        return found
    block = db.get(Block, inserted)
    assert block is not None
    expire_pair_batches(db, actor.account_id, subject_id)
    match, conversation = _end_relationship(db, actor.account_id, subject_id, now)
    write_audit(
        db,
        action="block.create",
        actor_id=actor.account_id,
        subject_account_id=subject_id,
        resource_type="blocks",
        resource_id=block.block_id,
        request_id=request_id_of() or "local",
        metadata={"reason_code": reason, "had_active_match": match is not None},
    )
    enqueue_event(
        db,
        _event_base(
            event_name="block",
            actor_id=actor.account_id,
            subject_id=subject_id,
            match=match,
            conversation=conversation,
            classification="product_pseudonymous",
            properties={
                "reason_code": reason,
                "had_active_match": match is not None,
            },
        ),
    )
    return block


def end_block(db: Session, actor: Account, block_id: UUID) -> None:
    block = db.scalar(
        select(Block).where(
            Block.block_id == block_id,
            Block.blocker_account_id == actor.account_id,
        )
    )
    if block is None:
        raise AppError(404, "not_found", "Not found.")
    lock_pair(db, block.blocker_account_id, block.blocked_account_id)
    if block.ended_at is not None:
        return
    block.ended_at = _now()
    write_audit(
        db,
        action="block.end",
        actor_id=actor.account_id,
        subject_account_id=block.blocked_account_id,
        resource_type="blocks",
        resource_id=block.block_id,
        request_id=request_id_of() or "local",
        metadata={},
    )


def list_blocks(
    db: Session, actor: Account, *, limit: int = _PAGE, after: str | None = None
) -> dict:
    bound = min(max(limit, 1), _PAGE)
    stmt = (
        select(Block, Profile)
        .join(Profile, Profile.account_id == Block.blocked_account_id)
        .where(
            Block.blocker_account_id == actor.account_id,
            Block.ended_at.is_(None),
        )
        .order_by(Block.created_at.desc(), Block.block_id.desc())
    )
    if after:
        try:
            marker_id = UUID(after)
        except ValueError:
            raise AppError(422, "validation_error", "Invalid request.") from None
        marker = db.get(Block, marker_id)
        if marker is None or marker.blocker_account_id != actor.account_id:
            raise AppError(404, "not_found", "Not found.")
        stmt = stmt.where(
            (Block.created_at < marker.created_at)
            | (
                (Block.created_at == marker.created_at)
                & (Block.block_id < marker.block_id)
            )
        )
    rows = list(db.execute(stmt.limit(bound + 1)).all())
    next_cursor = None
    if len(rows) > bound:
        rows = rows[:bound]
        next_cursor = str(rows[-1][0].block_id)
    return {
        "items": [
            {
                "block_id": str(block.block_id),
                "profile_id": str(profile.profile_id),
                "created_at": _iso(block.created_at),
            }
            for block, profile in rows
        ],
        "next_cursor": next_cursor,
    }


def create_report(
    db: Session,
    actor: Account,
    *,
    profile_id: UUID,
    message_id: UUID | None,
    reason_code: str,
    details: str | None,
) -> dict:
    profile = _subject_profile(db, profile_id, actor.account_id)
    stored_message_id = None
    conversation = None
    match = None
    if message_id is not None:
        from ai_dating.messaging.service import reportable_message

        row = reportable_message(db, actor.account_id, profile.account_id, message_id)
        stored_message_id = row.message_id
        conversation = db.get(Conversation, row.conversation_id)
        if conversation is not None:
            match = db.get(Match, conversation.match_id)
    reason = _reason(reason_code)
    text = None if details is None else details.strip() or None
    if text is not None and len(text) > 4000:
        raise AppError(422, "validation_error", "Invalid request.")
    now = _now()
    block = create_block(
        db,
        actor,
        profile_id=profile.profile_id,
        match_id=None,
        reason_code=reason,
    )
    report = Report(
        report_id=uuid4(),
        reporter_account_id=actor.account_id,
        subject_account_id=profile.account_id,
        message_id=stored_message_id,
        reason_code=reason,
        details=text,
        state="open",
        created_at=now,
        resolved_at=None,
    )
    db.add(report)
    db.flush()
    case = ModerationCase(
        case_id=uuid4(),
        report_id=report.report_id,
        subject_account_id=profile.account_id,
        source="report",
        severity=SEVERITY[reason],
        state="open",
        decision=None,
        assigned_staff_id=None,
        evidence_object_key=None,
        created_at=now,
        updated_at=now,
        resolved_at=None,
    )
    db.add(case)
    write_audit(
        db,
        action="report.create",
        actor_id=actor.account_id,
        subject_account_id=profile.account_id,
        resource_type="reports",
        resource_id=report.report_id,
        request_id=request_id_of() or "local",
        metadata={"reason_code": reason, "block_id": str(block.block_id)},
    )
    enqueue_event(
        db,
        _event_base(
            event_name="report",
            actor_id=actor.account_id,
            subject_id=profile.account_id,
            match=match,
            conversation=conversation,
            classification="security_restricted",
            properties={
                "report_id": str(report.report_id),
                "reason_code": reason,
                "target_type": "account",
            },
        ),
    )
    return {"report_id": str(report.report_id), "status": "received"}


def block_filter(actor_id: UUID):
    return ~exists(
        select(1).where(
            Block.ended_at.is_(None),
            or_(
                (Block.blocker_account_id == actor_id)
                & (Block.blocked_account_id == Account.account_id),
                (Block.blocker_account_id == Account.account_id)
                & (Block.blocked_account_id == actor_id),
            ),
        )
    )
