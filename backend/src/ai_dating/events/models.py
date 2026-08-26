from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class OutboxEvent(Base):
    # ponytail: no delivered-row GC (ceiling: table growth).
    # Upgrade: DELETE WHERE delivered_at < now() - interval '7 days'.
    __tablename__ = "outbox_events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer)
    aggregate_type: Mapped[str] = mapped_column(Text)
    aggregate_id: Mapped[UUID] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
