"""Profile facts, calibration, and AI operation metadata.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FACT_KEYS = (
    "interest_tags",
    "activity_style",
    "social_style",
    "communication_style",
    "schedule_preference",
)


def upgrade() -> None:
    op.create_table(
        "profile_facts",
        sa.Column("fact_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column("provenance_excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("review_state", sa.Text(), server_default="pending", nullable=False),
        sa.Column("visibility", sa.Text(), server_default="private", nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extractor_version", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column(
            "superseded_by_id",
            sa.Uuid(),
            sa.ForeignKey("profile_facts.fact_id"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "fact_key IN (" + ",".join(f"'{k}'" for k in _FACT_KEYS) + ")",
            name="ck_profile_facts_key",
        ),
        sa.CheckConstraint(
            "source_type IN ('form','free_text','user_edit')",
            name="ck_profile_facts_source",
        ),
        sa.CheckConstraint(
            "review_state IN ('pending','confirmed','rejected')",
            name="ck_profile_facts_review",
        ),
        sa.CheckConstraint(
            "visibility IN ('private','matching_only','eligible_only')",
            name="ck_profile_facts_visibility",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_profile_facts_confidence",
        ),
        sa.CheckConstraint(
            "source_type <> 'free_text' OR extractor_version IS NOT NULL",
            name="ck_profile_facts_extractor",
        ),
        sa.CheckConstraint(
            "provenance_excerpt IS NULL OR char_length(provenance_excerpt) <= 120",
            name="ck_profile_facts_excerpt",
        ),
    )
    op.create_index(
        "one_current_fact",
        "profile_facts",
        ["profile_id", "fact_key"],
        unique=True,
        postgresql_where=sa.text(
            "superseded_at IS NULL AND review_state <> 'rejected'"
        ),
    )
    op.create_index(
        "ix_profile_facts_profile_state",
        "profile_facts",
        ["profile_id", "review_state"],
    )
    op.create_table(
        "calibration_sessions",
        sa.Column("calibration_session_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calibration_version", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="started", nullable=False),
        sa.Column(
            "synthetic_only", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "signal_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('started','completed','skipped')",
            name="ck_calibration_sessions_state",
        ),
        sa.UniqueConstraint(
            "account_id",
            "calibration_version",
            name="uq_calibration_sessions_account_version",
        ),
    )
    op.create_table(
        "calibration_choices",
        sa.Column("calibration_choice_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "calibration_session_id",
            sa.Uuid(),
            sa.ForeignKey(
                "calibration_sessions.calibration_session_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("demo_pair_id", sa.Text(), nullable=False),
        sa.Column("selection", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "selection IN ('left','right','neither')",
            name="ck_calibration_choices_selection",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('shared_interests','communication_style','activity_style',"
            "'schedule_fit','other')",
            name="ck_calibration_choices_reason",
        ),
        sa.UniqueConstraint(
            "calibration_session_id",
            "demo_pair_id",
            name="uq_calibration_choices_pair",
        ),
    )
    op.create_table(
        "ai_operations",
        sa.Column("ai_operation_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("background_jobs.job_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("source_entity_type", sa.Text(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_input", sa.Integer(), nullable=True),
        sa.Column("token_output", sa.Integer(), nullable=True),
        sa.Column("result_status", sa.Text(), nullable=False),
        sa.Column("safety_result", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation_type IN ('extraction')",
            name="ck_ai_operations_type",
        ),
        sa.CheckConstraint(
            "result_status IN "
            "('succeeded','schema_invalid','safety_rejected','provider_error','stale')",
            name="ck_ai_operations_result",
        ),
        sa.CheckConstraint(
            "safety_result IN ('passed','rejected','skipped')",
            name="ck_ai_operations_safety",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_operations")
    op.drop_table("calibration_choices")
    op.drop_table("calibration_sessions")
    op.drop_index("ix_profile_facts_profile_state", table_name="profile_facts")
    op.drop_index("one_current_fact", table_name="profile_facts")
    op.drop_table("profile_facts")
