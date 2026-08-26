"""Blocks, reports, moderation cases, and relationship rows.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REASONS = "('harassment','spam','fake_profile','underage','other')"


def upgrade() -> None:
    op.create_table(
        "blocks",
        sa.Column("block_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "blocker_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blocked_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "blocker_account_id <> blocked_account_id",
            name="ck_blocks_distinct",
        ),
        sa.CheckConstraint(
            f"reason_code IS NULL OR reason_code IN {_REASONS}",
            name="ck_blocks_reason",
        ),
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX one_active_block "
            "ON blocks (blocker_account_id, blocked_account_id) "
            "WHERE ended_at IS NULL"
        )
    )
    op.create_index(
        "ix_blocks_blocked_active",
        "blocks",
        ["blocked_account_id"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "matches",
        sa.Column("match_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_low_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_high_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_account_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "account_low_id <> account_high_id", name="ck_matches_distinct"
        ),
        sa.CheckConstraint("account_low_id < account_high_id", name="ck_matches_order"),
        sa.CheckConstraint(
            "state IN ('active','unmatched','blocked')", name="ck_matches_state"
        ),
        sa.UniqueConstraint(
            "account_low_id", "account_high_id", name="uq_matches_pair"
        ),
    )
    op.create_index("ix_matches_low_state", "matches", ["account_low_id", "state"])
    op.create_index("ix_matches_high_state", "matches", ["account_high_id", "state"])
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "match_id",
            sa.Uuid(),
            sa.ForeignKey("matches.match_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("match_id", name="uq_conversations_match"),
        sa.CheckConstraint(
            "state IN ('active','closed')", name="ck_conversations_state"
        ),
    )
    op.create_table(
        "reports",
        sa.Column("report_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "reporter_account_id",
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
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reporter_account_id <> subject_account_id",
            name="ck_reports_distinct",
        ),
        sa.CheckConstraint(f"reason_code IN {_REASONS}", name="ck_reports_reason"),
        sa.CheckConstraint(
            "state IN ('open','triaged','resolved','dismissed')",
            name="ck_reports_state",
        ),
        sa.CheckConstraint(
            "details IS NULL OR char_length(details) <= 4000",
            name="ck_reports_details",
        ),
    )
    op.create_index("ix_reports_state_created", "reports", ["state", "created_at"])
    op.create_index(
        "ix_reports_subject_created", "reports", ["subject_account_id", "created_at"]
    )
    op.create_table(
        "moderation_cases",
        sa.Column("case_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("reports.report_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "subject_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="open", nullable=False),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("assigned_staff_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_object_key", sa.Text(), nullable=True),
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
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("report_id", name="uq_moderation_cases_report"),
        sa.CheckConstraint(
            "source IN ('report','automated','staff')",
            name="ck_moderation_cases_source",
        ),
        sa.CheckConstraint(
            "state IN ('open','reviewing','resolved')",
            name="ck_moderation_cases_state",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_moderation_cases_severity",
        ),
    )
    op.create_index(
        "ix_moderation_cases_queue",
        "moderation_cases",
        ["state", "severity", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_moderation_cases_queue", table_name="moderation_cases")
    op.drop_table("moderation_cases")
    op.drop_index("ix_reports_subject_created", table_name="reports")
    op.drop_index("ix_reports_state_created", table_name="reports")
    op.drop_table("reports")
    op.drop_table("conversations")
    op.drop_index("ix_matches_high_state", table_name="matches")
    op.drop_index("ix_matches_low_state", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_blocks_blocked_active", table_name="blocks")
    op.execute(sa.text("DROP INDEX IF EXISTS one_active_block"))
    op.drop_table("blocks")
