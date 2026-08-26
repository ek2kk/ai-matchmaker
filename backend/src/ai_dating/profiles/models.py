from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base
from ai_dating.database.vector import Vector


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender_code: Mapped[str] = mapped_column(Text)
    orientation_code: Mapped[str] = mapped_column(Text)
    search_mode: Mapped[str] = mapped_column(Text, default="dating")
    relationship_goal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_status: Mapped[str] = mapped_column(Text, default="single")
    city_code: Mapped[str] = mapped_column(Text, default="moscow")
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    public_area_code: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, default="hidden")
    moderation_state: Mapped[str] = mapped_column(Text, default="pending")
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completion_percent: Mapped[int] = mapped_column(SmallInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DatingPreferences(Base):
    __tablename__ = "dating_preferences"

    account_id: Mapped[UUID] = mapped_column(primary_key=True)
    search_mode: Mapped[str] = mapped_column(Text, default="dating")
    accepted_gender_codes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    age_min: Mapped[int] = mapped_column(SmallInteger)
    age_max: Mapped[int] = mapped_column(SmallInteger)
    max_distance_km: Mapped[int] = mapped_column(SmallInteger)
    city_codes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    relationship_goal_codes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    dealbreakers: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProfileAnswer(Base):
    __tablename__ = "profile_answers"

    answer_id: Mapped[UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[UUID]
    prompt_code: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, default="eligible_only")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProfileFact(Base):
    __tablename__ = "profile_facts"

    fact_id: Mapped[UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[UUID]
    profile_side: Mapped[str] = mapped_column(Text)
    fact_code: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    preference_strength: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(Text)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    review_state: Mapped[str] = mapped_column(Text, default="pending")
    visibility: Mapped[str] = mapped_column(Text, default="private")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extractor_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profile_facts.fact_id"), nullable=True
    )


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    embedding_id: Mapped[UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(Text)
    source_version: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(Text)
    projection_schema_version: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
