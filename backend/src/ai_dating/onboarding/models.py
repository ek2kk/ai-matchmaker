from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class OnboardingStepCompletion(Base):
    __tablename__ = "onboarding_step_completions"

    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    flow_version: Mapped[str] = mapped_column(Text, primary_key=True)
    step_code: Mapped[str] = mapped_column(Text, primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferences_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CalibrationSession(Base):
    __tablename__ = "calibration_sessions"

    calibration_session_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID]
    calibration_version: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, default="started")
    synthetic_only: Mapped[bool] = mapped_column(Boolean, default=True)
    signal_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CalibrationChoice(Base):
    __tablename__ = "calibration_choices"

    calibration_choice_id: Mapped[UUID] = mapped_column(primary_key=True)
    calibration_session_id: Mapped[UUID]
    demo_pair_id: Mapped[str] = mapped_column(Text)
    selection: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
