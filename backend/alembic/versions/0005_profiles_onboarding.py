"""Profiles, preferences, answers, onboarding steps.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
    op.create_table(
        "profiles",
        sa.Column("profile_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("gender_code", sa.Text(), nullable=False),
        sa.Column("orientation_code", sa.Text(), nullable=False),
        sa.Column("relationship_goal_code", sa.Text(), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("public_area_code", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), server_default="hidden", nullable=False),
        sa.Column(
            "moderation_state", sa.Text(), server_default="pending", nullable=False
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "completion_percent", sa.SmallInteger(), server_default="0", nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            "char_length(display_name) BETWEEN 1 AND 80",
            name="ck_profiles_display_name",
        ),
        sa.CheckConstraint(
            "bio IS NULL OR char_length(bio) <= 2000",
            name="ck_profiles_bio",
        ),
        sa.CheckConstraint(
            "gender_code IN ('man','woman')",
            name="ck_profiles_gender",
        ),
        sa.CheckConstraint(
            "orientation_code IN ('heterosexual')",
            name="ck_profiles_orientation",
        ),
        sa.CheckConstraint(
            "relationship_goal_code IN "
            "('serious_relationship','friends_with_benefits','unsure')",
            name="ck_profiles_goal",
        ),
        sa.CheckConstraint(
            "visibility IN ('hidden','eligible','paused')",
            name="ck_profiles_visibility",
        ),
        sa.CheckConstraint(
            "moderation_state IN ('pending','approved','rejected','suspended')",
            name="ck_profiles_moderation",
        ),
        sa.CheckConstraint(
            "completion_percent BETWEEN 0 AND 100",
            name="ck_profiles_completion",
        ),
        sa.CheckConstraint("version >= 1", name="ck_profiles_version"),
    )
    op.create_index("ix_profiles_public_area", "profiles", ["public_area_code"])
    op.create_index(
        "ix_profiles_visibility_moderation_updated",
        "profiles",
        ["visibility", "moderation_state", "updated_at"],
    )
    op.create_index(
        "ix_profiles_location",
        "profiles",
        ["location"],
        postgresql_using="gist",
    )
    op.create_table(
        "dating_preferences",
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "accepted_gender_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column("age_min", sa.SmallInteger(), nullable=False),
        sa.Column("age_max", sa.SmallInteger(), nullable=False),
        sa.Column("max_distance_km", sa.SmallInteger(), nullable=False),
        sa.Column(
            "relationship_goal_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "dealbreakers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            "cardinality(accepted_gender_codes) >= 1",
            name="ck_prefs_genders",
        ),
        sa.CheckConstraint(
            "cardinality(relationship_goal_codes) >= 1",
            name="ck_prefs_goals",
        ),
        sa.CheckConstraint(
            "age_min >= 18 AND age_max <= 120 AND age_min <= age_max",
            name="ck_prefs_age",
        ),
        sa.CheckConstraint(
            "max_distance_km BETWEEN 1 AND 500",
            name="ck_prefs_distance",
        ),
        sa.CheckConstraint("version >= 1", name="ck_prefs_version"),
    )
    op.create_index(
        "ix_dating_preferences_updated",
        "dating_preferences",
        ["updated_at"],
    )
    op.create_table(
        "profile_answers",
        sa.Column("answer_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_code", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column(
            "visibility", sa.Text(), server_default="eligible_only", nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            "char_length(answer_text) BETWEEN 1 AND 1000",
            name="ck_answers_text",
        ),
        sa.CheckConstraint(
            "visibility IN ('private','matching_only','eligible_only')",
            name="ck_answers_visibility",
        ),
        sa.CheckConstraint("version >= 1", name="ck_answers_version"),
    )
    op.create_index(
        "uq_profile_answers_prompt",
        "profile_answers",
        ["profile_id", "prompt_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "onboarding_step_completions",
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.account_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("flow_version", sa.Text(), nullable=False),
        sa.Column("step_code", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("preferences_version", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            "account_id", "flow_version", "step_code", name="pk_onboarding_steps"
        ),
        sa.CheckConstraint(
            "step_code IN ('account','profile','preferences','photos',"
            "'facts_review','calibration')",
            name="ck_onboarding_step_code",
        ),
    )


def downgrade() -> None:
    op.drop_table("onboarding_step_completions")
    op.drop_index("uq_profile_answers_prompt", table_name="profile_answers")
    op.drop_table("profile_answers")
    op.drop_index("ix_dating_preferences_updated", table_name="dating_preferences")
    op.drop_table("dating_preferences")
    op.drop_index("ix_profiles_location", table_name="profiles")
    op.drop_index("ix_profiles_visibility_moderation_updated", table_name="profiles")
    op.drop_index("ix_profiles_public_area", table_name="profiles")
    op.drop_table("profiles")
