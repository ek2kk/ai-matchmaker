from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class Like(Base):
    __tablename__ = "likes"

    like_id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_account_id: Mapped[UUID]
    subject_account_id: Mapped[UUID]
    recommendation_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_items.recommendation_item_id")
    )
    recommendation_action_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_actions.action_id")
    )
    state: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.conversation_id"), primary_key=True
    )
    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_read_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.message_id"), nullable=True
    )
