"""Allow embedding rows in ai_operations.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction','embedding')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction')",
    )
