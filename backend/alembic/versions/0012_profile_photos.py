"""Private profile photos and upload intents.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_upload_intents",
        sa.Column("upload_intent_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("photo_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("object_key", name="uq_photo_upload_intents_key"),
        sa.CheckConstraint(
            "status IN ('pending','completed','expired')",
            name="ck_photo_upload_intents_status",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_photo_upload_intents_size"),
    )
    op.create_index(
        "ix_photo_upload_intents_account_created",
        "photo_upload_intents",
        ["account_id", sa.text("created_at DESC")],
    )
    op.create_table(
        "profile_photos",
        sa.Column("photo_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("derived_object_key", sa.Text(), nullable=True),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "moderation_state", sa.Text(), server_default="pending", nullable=False
        ),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("object_key", name="uq_profile_photos_object_key"),
        sa.CheckConstraint(
            "moderation_state IN ('pending','approved','rejected')",
            name="ck_profile_photos_moderation",
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 5", name="ck_profile_photos_position"
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_profile_photos_size"),
        sa.CheckConstraint("version > 0", name="ck_profile_photos_version"),
        sa.CheckConstraint(
            "width IS NULL OR width > 0", name="ck_profile_photos_width"
        ),
        sa.CheckConstraint(
            "height IS NULL OR height > 0", name="ck_profile_photos_height"
        ),
    )
    op.create_index(
        "ix_profile_photos_profile_state",
        "profile_photos",
        ["profile_id", "moderation_state"],
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_profile_photos_position "
            "ON profile_photos (profile_id, position) "
            "WHERE deleted_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_profile_photos_derived_key "
            "ON profile_photos (derived_object_key) "
            "WHERE derived_object_key IS NOT NULL"
        )
    )
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction','embedding','moderation')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ai_operations_type", "ai_operations", type_="check")
    op.create_check_constraint(
        "ck_ai_operations_type",
        "ai_operations",
        "operation_type IN ('extraction','embedding')",
    )
    op.execute(sa.text("DROP INDEX IF EXISTS uq_profile_photos_derived_key"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_profile_photos_position"))
    op.drop_index("ix_profile_photos_profile_state", table_name="profile_photos")
    op.drop_table("profile_photos")
    op.drop_index(
        "ix_photo_upload_intents_account_created", table_name="photo_upload_intents"
    )
    op.drop_table("photo_upload_intents")
