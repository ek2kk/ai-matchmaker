"""Telegram identities use one-time hashed invites.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_invites",
        sa.Column("invite_id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "admitted_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_invites_active", "auth_invites", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_invites_active", table_name="auth_invites")
    op.drop_table("auth_invites")
