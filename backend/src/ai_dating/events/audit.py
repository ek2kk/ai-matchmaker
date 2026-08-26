from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from ai_dating.database.base import Base


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_log"

    audit_id: Mapped[UUID] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[UUID | None]
    subject_account_id: Mapped[UUID | None]
    resource_type: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[UUID | None]
    request_id: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def write_audit(
    session: Session,
    *,
    action: str,
    actor_id: UUID | None,
    subject_account_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None,
    request_id: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        SecurityAuditLog(
            audit_id=uuid4(),
            action=action,
            actor_type="account" if actor_id else "system",
            actor_id=actor_id,
            subject_account_id=subject_account_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            metadata_json=metadata or {},
            occurred_at=datetime.now(UTC),
        )
    )
