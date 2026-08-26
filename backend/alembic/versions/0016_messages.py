"""Messages table and read/report foreign keys.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("message_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_message_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("moderation_state", sa.Text(), server_default="held", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("allowed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 4000", name="ck_messages_body_len"
        ),
        sa.CheckConstraint(
            "moderation_state IN ('allowed','held','rejected')",
            name="ck_messages_moderation_state",
        ),
        sa.UniqueConstraint(
            "sender_account_id",
            "client_message_id",
            name="uq_messages_sender_client",
        ),
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_messages_allowed_cursor ON messages "
            "(conversation_id, allowed_at, message_id) "
            "WHERE moderation_state = 'allowed'"
        )
    )
    op.create_foreign_key(
        "fk_conversation_members_last_read",
        "conversation_members",
        "messages",
        ["last_read_message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reports_message",
        "reports",
        "messages",
        ["message_id"],
        ["message_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reports_message", "reports", type_="foreignkey")
    op.drop_constraint(
        "fk_conversation_members_last_read",
        "conversation_members",
        type_="foreignkey",
    )
    op.execute(sa.text("DROP INDEX IF EXISTS ix_messages_allowed_cursor"))
    op.drop_table("messages")
