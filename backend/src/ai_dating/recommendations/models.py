from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class RecommendationBatch(Base):
    __tablename__ = "recommendation_batches"

    recommendation_batch_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_account_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(Text, default="building")
    generation_key: Mapped[str] = mapped_column(Text)
    batch_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    input_snapshot: Mapped[dict] = mapped_column(JSONB)
    eligibility_version: Mapped[str] = mapped_column(Text)
    ranker_version: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_mode: Mapped[str] = mapped_column(Text, default="none")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    recommendation_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    recommendation_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_batches.recommendation_batch_id")
    )
    candidate_account_id: Mapped[UUID]
    item_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    rank: Mapped[int] = mapped_column(SmallInteger)
    semantic_actor: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    semantic_candidate: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5), nullable=True
    )
    goal_alignment: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    prompt_fact_overlap: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5), nullable=True
    )
    distance_decay: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    activity_freshness: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5), nullable=True
    )
    profile_quality: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 5), nullable=True
    )
    final_score: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    public_profile_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    candidate_profile_version: Mapped[int] = mapped_column(Integer)
    candidate_embedding_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecommendationExposure(Base):
    __tablename__ = "recommendation_exposures"

    exposure_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_account_id: Mapped[UUID]
    candidate_account_id: Mapped[UUID]
    recommendation_item_id: Mapped[UUID]
    impressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_surface: Mapped[str] = mapped_column(Text)


class RecommendationAction(Base):
    __tablename__ = "recommendation_actions"

    action_id: Mapped[UUID] = mapped_column(primary_key=True)
    recommendation_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendation_items.recommendation_item_id")
    )
    actor_account_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
