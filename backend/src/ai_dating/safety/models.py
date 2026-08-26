from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class Block(Base):
    __tablename__ = "blocks"

    block_id: Mapped[UUID] = mapped_column(primary_key=True)
    blocker_account_id: Mapped[UUID]
    blocked_account_id: Mapped[UUID]
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_low_id: Mapped[UUID]
    account_high_id: Mapped[UUID]
    state: Mapped[str] = mapped_column(Text, default="active")
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_by_account_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_like_low_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_like_high_id: Mapped[UUID | None] = mapped_column(nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[UUID] = mapped_column(primary_key=True)
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.match_id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"

    report_id: Mapped[UUID] = mapped_column(primary_key=True)
    reporter_account_id: Mapped[UUID]
    subject_account_id: Mapped[UUID]
    message_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason_code: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModerationCase(Base):
    __tablename__ = "moderation_cases"

    case_id: Mapped[UUID] = mapped_column(primary_key=True)
    report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reports.report_id", ondelete="SET NULL"), nullable=True
    )
    subject_account_id: Mapped[UUID]
    source: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, default="open")
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_staff_id: Mapped[UUID | None] = mapped_column(nullable=True)
    evidence_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
