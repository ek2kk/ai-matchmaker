"""Accounts, local auth, consents, jobs, idempotency.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.Text(), server_default="onboarding", nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('onboarding','active','paused','suspended',"
            "'deletion_pending','deleted')",
            name="ck_accounts_status",
        ),
        sa.CheckConstraint(
            "status = 'onboarding' OR date_of_birth IS NOT NULL",
            name="ck_accounts_dob_when_active",
        ),
        sa.CheckConstraint(
            "status NOT IN ('deleted','deletion_pending') OR deleted_at IS NOT NULL",
            name="ck_accounts_deleted_at",
        ),
    )
    op.create_table(
        "auth_identities",
        sa.Column("identity_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity"),
    )
    op.create_table(
        "auth_password_credentials",
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_sessions_account", "auth_sessions", ["account_id"])
    op.create_table(
        "consents",
        sa.Column("consent_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('granted','rejected','withdrawn')",
            name="ck_consents_decision",
        ),
    )
    op.create_index(
        "ix_consents_account_purpose_occurred",
        "consents",
        ["account_id", "purpose", "occurred_at"],
    )
    op.create_table(
        "privacy_controls",
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("discoverable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "show_distance", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "allow_ai_matching", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "allow_product_analytics",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("idempotency_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_status", sa.SmallInteger(), nullable=True),
        sa.Column(
            "response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_idempotency_public",
        "idempotency_keys",
        ["scope", "key"],
        unique=True,
        postgresql_where=sa.text("account_id IS NULL"),
    )
    op.create_index(
        "uq_idempotency_account",
        "idempotency_keys",
        ["account_id", "scope", "key"],
        unique=True,
        postgresql_where=sa.text("account_id IS NOT NULL"),
    )
    op.create_index("ix_idempotency_expires", "idempotency_keys", ["expires_at"])
    op.create_table(
        "background_jobs",
        sa.Column("job_id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "max_attempts", sa.SmallInteger(), server_default="8", nullable=False
        ),
        sa.Column(
            "run_after",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
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
            "status IN ('queued','running','succeeded','failed')",
            name="ck_background_jobs_status",
        ),
    )
    op.create_index(
        "ix_background_jobs_claim",
        "background_jobs",
        ["status", "run_after"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_table("background_jobs")
    op.drop_index("ix_idempotency_expires", table_name="idempotency_keys")
    op.drop_index("uq_idempotency_account", table_name="idempotency_keys")
    op.drop_index("uq_idempotency_public", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_table("privacy_controls")
    op.drop_index("ix_consents_account_purpose_occurred", table_name="consents")
    op.drop_table("consents")
    op.drop_index("ix_auth_sessions_account", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("auth_password_credentials")
    op.drop_table("auth_identities")
    op.drop_table("accounts")
