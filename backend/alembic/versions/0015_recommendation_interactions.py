"""Recommendation actions, likes, and conversation members.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PASS_REASONS = "('not_my_type','photos','location','other')"


def upgrade() -> None:
    op.create_table(
        "recommendation_actions",
        sa.Column("action_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_item_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendation_items.recommendation_item_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "recommendation_item_id",
            "actor_account_id",
            "action",
            name="uq_recommendation_actions_item_actor_action",
        ),
        sa.CheckConstraint(
            "action IN ('open','like','pass')",
            name="ck_recommendation_actions_action",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR ("
            "action = 'pass' AND reason_code IN " + _PASS_REASONS + ")",
            name="ck_recommendation_actions_reason",
        ),
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX one_terminal_recommendation_action "
            "ON recommendation_actions (recommendation_item_id, actor_account_id) "
            "WHERE action IN ('like','pass')"
        )
    )
    op.create_table(
        "likes",
        sa.Column("like_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recommendation_item_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendation_items.recommendation_item_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "recommendation_action_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendation_actions.action_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_account_id <> subject_account_id",
            name="ck_likes_distinct",
        ),
        sa.CheckConstraint("state IN ('active','withdrawn')", name="ck_likes_state"),
        sa.UniqueConstraint(
            "actor_account_id",
            "subject_account_id",
            name="uq_likes_pair",
        ),
        sa.UniqueConstraint(
            "recommendation_action_id",
            name="uq_likes_action",
        ),
    )
    op.create_index("ix_likes_subject_state", "likes", ["subject_account_id", "state"])
    op.add_column(
        "matches",
        sa.Column(
            "source_like_low_id",
            sa.Uuid(),
            sa.ForeignKey("likes.like_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "source_like_high_id",
            sa.Uuid(),
            sa.ForeignKey("likes.like_id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_table(
        "conversation_members",
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_read_message_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("conversation_members")
    op.drop_column("matches", "source_like_high_id")
    op.drop_column("matches", "source_like_low_id")
    op.drop_index("ix_likes_subject_state", table_name="likes")
    op.drop_table("likes")
    op.execute(sa.text("DROP INDEX IF EXISTS one_terminal_recommendation_action"))
    op.drop_table("recommendation_actions")
