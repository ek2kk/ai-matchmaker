"""Recommendation batch cache for the prototype worker.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_batches",
        sa.Column("recommendation_batch_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="building", nullable=False),
        sa.Column("generation_key", sa.Text(), nullable=False),
        sa.Column(
            "batch_schema_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "input_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("eligibility_version", sa.Text(), nullable=False),
        sa.Column("ranker_version", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("fallback_mode", sa.Text(), server_default="none", nullable=False),
        sa.Column("candidate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("generation_key", name="uq_recommendation_generation_key"),
        sa.CheckConstraint(
            "status IN ('building','ready','served','expired','failed')",
            name="ck_recommendation_batches_status",
        ),
        sa.CheckConstraint(
            "fallback_mode IN ('none','no_llm','no_embedding','insufficient_supply')",
            name="ck_recommendation_batches_fallback",
        ),
        sa.CheckConstraint(
            "batch_schema_version > 0",
            name="ck_recommendation_batches_schema",
        ),
        sa.CheckConstraint(
            "candidate_count >= 0 AND item_count >= 0 AND item_count <= 5",
            name="ck_recommendation_batches_counts",
        ),
    )
    op.create_index(
        "ix_recommendation_batches_owner_status_expires",
        "recommendation_batches",
        ["owner_account_id", "status", sa.text("expires_at DESC")],
    )
    op.create_table(
        "recommendation_items",
        sa.Column("recommendation_item_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_batch_id",
            sa.Uuid(),
            sa.ForeignKey(
                "recommendation_batches.recommendation_batch_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "candidate_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_schema_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("semantic_actor", sa.Numeric(6, 5), nullable=True),
        sa.Column("semantic_candidate", sa.Numeric(6, 5), nullable=True),
        sa.Column("goal_alignment", sa.Numeric(6, 5), nullable=True),
        sa.Column("prompt_fact_overlap", sa.Numeric(6, 5), nullable=True),
        sa.Column("distance_decay", sa.Numeric(6, 5), nullable=True),
        sa.Column("activity_freshness", sa.Numeric(6, 5), nullable=True),
        sa.Column("profile_quality", sa.Numeric(6, 5), nullable=True),
        sa.Column("final_score", sa.Numeric(6, 5), nullable=False),
        sa.Column(
            "public_profile_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "reason_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("candidate_profile_version", sa.Integer(), nullable=False),
        sa.Column("candidate_embedding_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "recommendation_batch_id",
            "candidate_account_id",
            name="uq_recommendation_items_candidate",
        ),
        sa.UniqueConstraint(
            "recommendation_batch_id",
            "rank",
            name="uq_recommendation_items_rank",
        ),
        sa.CheckConstraint(
            "item_schema_version > 0",
            name="ck_recommendation_items_schema",
        ),
        sa.CheckConstraint("rank BETWEEN 1 AND 5", name="ck_recommendation_items_rank"),
    )
    op.create_index(
        "ix_recommendation_items_candidate",
        "recommendation_items",
        ["candidate_account_id"],
    )
    op.create_table(
        "recommendation_exposures",
        sa.Column("exposure_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_account_id",
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
            unique=True,
        ),
        sa.Column(
            "impressed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("client_surface", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "owner_account_id <> candidate_account_id",
            name="ck_recommendation_exposures_pair",
        ),
        sa.UniqueConstraint(
            "owner_account_id",
            "candidate_account_id",
            name="uq_recommendation_exposures_pair",
        ),
    )


def downgrade() -> None:
    op.drop_table("recommendation_exposures")
    op.drop_index(
        "ix_recommendation_items_candidate", table_name="recommendation_items"
    )
    op.drop_table("recommendation_items")
    op.drop_index(
        "ix_recommendation_batches_owner_status_expires",
        table_name="recommendation_batches",
    )
    op.drop_table("recommendation_batches")
