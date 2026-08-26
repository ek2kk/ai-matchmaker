from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base

LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(Text, default="onboarding")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
