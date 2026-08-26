from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base

PRIVACY_POLICY_VERSION = "2026-08-26"
PURPOSES = frozenset(
    {
        "terms_privacy",
        "dating_visibility",
        "ai_matching",
        "product_analytics",
        "model_improvement",
        "calibration",
    }
)
DECISIONS = frozenset({"granted", "rejected", "withdrawn"})


class Consent(Base):
    __tablename__ = "consents"

    consent_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID]
    purpose: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(Text)


class PrivacyControls(Base):
    __tablename__ = "privacy_controls"

    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=False)
    show_distance: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_ai_matching: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_product_analytics: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    job_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="queued")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=8)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
