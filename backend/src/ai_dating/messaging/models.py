from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[UUID] = mapped_column(primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.conversation_id")
    )
    sender_account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.account_id"))
    client_message_id: Mapped[UUID]
    body: Mapped[str] = mapped_column(Text)
    moderation_state: Mapped[str] = mapped_column(Text, default="held")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    allowed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
