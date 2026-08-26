from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_dating.database.base import Base


class AiOperation(Base):
    __tablename__ = "ai_operations"

    ai_operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    job_id: Mapped[UUID | None] = mapped_column(nullable=True)
    operation_type: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text)
    source_entity_type: Mapped[str] = mapped_column(Text)
    source_entity_id: Mapped[UUID]
    source_version: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_rub: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    result_status: Mapped[str] = mapped_column(Text)
    safety_result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
