"""Rerank operation type and estimated cost.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction','embedding','moderation','rerank')",
    )
    op.add_column(
        "ai_operations",
        sa.Column("estimated_cost_rub", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_operations", "estimated_cost_rub")
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction','embedding','moderation')",
    )
