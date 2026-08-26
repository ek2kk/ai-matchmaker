"""Restricted security audit log.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_audit_log",
        sa.Column("audit_id", sa.Uuid(), primary_key=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("subject_account_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_security_audit_subject_occurred",
        "security_audit_log",
        ["subject_account_id", "occurred_at"],
    )
    op.create_index(
        "ix_security_audit_action_occurred",
        "security_audit_log",
        ["action", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_audit_action_occurred", table_name="security_audit_log")
    op.drop_index("ix_security_audit_subject_occurred", table_name="security_audit_log")
    op.drop_table("security_audit_log")
