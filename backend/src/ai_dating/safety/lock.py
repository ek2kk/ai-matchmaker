from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def canonical_pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    return (left, right) if left.int < right.int else (right, left)


def lock_pair(db: Session, left: UUID, right: UUID) -> None:
    low, high = canonical_pair(left, right)
    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "('x' || substr(md5(:pair), 1, 16))::bit(64)::bigint)"
        ),
        {"pair": f"{low}:{high}"},
    )
