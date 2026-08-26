"""Hard fields, sided facts, and closed fact_code values.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FACT_CODES = (
    "interest",
    "date_preference",
    "values",
    "fitness_level",
    "nightlife_preference",
    "travel_frequency",
    "social_style",
    "energy_level",
    "spontaneity",
    "communication_style",
    "occupation_domain",
)


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "search_mode",
            sa.Text(),
            nullable=False,
            server_default="dating",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "relationship_status",
            sa.Text(),
            nullable=False,
            server_default="single",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "city_code",
            sa.Text(),
            nullable=False,
            server_default="moscow",
        ),
    )
    op.alter_column("profiles", "relationship_goal_code", nullable=True)
    op.drop_constraint("ck_profiles_goal", "profiles", type_="check")
    op.create_check_constraint(
        "ck_profiles_search_mode",
        "profiles",
        "search_mode IN ('dating','friendship')",
    )
    op.create_check_constraint(
        "ck_profiles_relationship_status",
        "profiles",
        "relationship_status IN ('single')",
    )
    op.create_check_constraint(
        "ck_profiles_city",
        "profiles",
        "city_code IN ('moscow')",
    )
    op.create_check_constraint(
        "ck_profiles_goal",
        "profiles",
        "("
        "search_mode = 'dating' AND relationship_goal_code IN "
        "('serious_relationship','friends_with_benefits','unsure')"
        ") OR ("
        "search_mode = 'friendship' AND relationship_goal_code IS NULL"
        ")",
    )
    op.alter_column("profiles", "search_mode", server_default=None)
    op.alter_column("profiles", "relationship_status", server_default=None)
    op.alter_column("profiles", "city_code", server_default=None)

    op.add_column(
        "dating_preferences",
        sa.Column(
            "search_mode",
            sa.Text(),
            nullable=False,
            server_default="dating",
        ),
    )
    op.add_column(
        "dating_preferences",
        sa.Column(
            "city_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY['moscow']::text[]"),
        ),
    )
    op.drop_constraint("ck_prefs_goals", "dating_preferences", type_="check")
    op.create_check_constraint(
        "ck_prefs_search_mode",
        "dating_preferences",
        "search_mode IN ('dating','friendship')",
    )
    op.create_check_constraint(
        "ck_prefs_cities",
        "dating_preferences",
        "cardinality(city_codes) >= 1",
    )
    op.create_check_constraint(
        "ck_prefs_goals",
        "dating_preferences",
        "("
        "search_mode = 'dating' AND cardinality(relationship_goal_codes) >= 1"
        ") OR search_mode = 'friendship'",
    )
    op.alter_column("dating_preferences", "search_mode", server_default=None)
    op.alter_column("dating_preferences", "city_codes", server_default=None)

    op.execute(sa.text("DELETE FROM profile_facts"))
    op.drop_index("one_current_fact", table_name="profile_facts")
    op.drop_constraint("ck_profile_facts_key", "profile_facts", type_="check")
    op.alter_column("profile_facts", "fact_key", new_column_name="fact_code")
    op.alter_column(
        "profile_facts",
        "value",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        postgresql_using="value::text",
    )
    op.add_column(
        "profile_facts",
        sa.Column(
            "profile_side",
            sa.Text(),
            nullable=False,
            server_default="self",
        ),
    )
    op.add_column(
        "profile_facts",
        sa.Column("preference_strength", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_profile_facts_key",
        "profile_facts",
        "fact_code IN (" + ",".join(f"'{k}'" for k in _FACT_CODES) + ")",
    )
    op.create_check_constraint(
        "ck_profile_facts_side",
        "profile_facts",
        "profile_side IN ('self','desired_partner')",
    )
    op.create_check_constraint(
        "ck_profile_facts_strength",
        "profile_facts",
        "("
        "profile_side = 'self' AND preference_strength IS NULL"
        ") OR ("
        "profile_side = 'desired_partner' AND preference_strength IN "
        "('dont_care','prefer','strong_preference')"
        ")",
    )
    op.create_index(
        "one_current_fact",
        "profile_facts",
        ["profile_id", "profile_side", "fact_code", "value"],
        unique=True,
        postgresql_where=sa.text(
            "superseded_at IS NULL AND review_state <> 'rejected'"
        ),
    )
    op.alter_column("profile_facts", "profile_side", server_default=None)


def downgrade() -> None:
    op.drop_index("one_current_fact", table_name="profile_facts")
    op.drop_constraint("ck_profile_facts_strength", "profile_facts", type_="check")
    op.drop_constraint("ck_profile_facts_side", "profile_facts", type_="check")
    op.drop_constraint("ck_profile_facts_key", "profile_facts", type_="check")
    op.drop_column("profile_facts", "preference_strength")
    op.drop_column("profile_facts", "profile_side")
    op.alter_column(
        "profile_facts",
        "value",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using="'{}'::jsonb",
    )
    op.alter_column("profile_facts", "fact_code", new_column_name="fact_key")
    op.create_check_constraint(
        "ck_profile_facts_key",
        "profile_facts",
        "fact_key IN ('interest_tags','activity_style','social_style',"
        "'communication_style','schedule_preference')",
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
    op.drop_constraint("ck_prefs_goals", "dating_preferences", type_="check")
    op.drop_constraint("ck_prefs_cities", "dating_preferences", type_="check")
    op.drop_constraint("ck_prefs_search_mode", "dating_preferences", type_="check")
    op.drop_column("dating_preferences", "city_codes")
    op.drop_column("dating_preferences", "search_mode")
    op.create_check_constraint(
        "ck_prefs_goals",
        "dating_preferences",
        "cardinality(relationship_goal_codes) >= 1",
    )
    op.drop_constraint("ck_profiles_goal", "profiles", type_="check")
    op.drop_constraint("ck_profiles_city", "profiles", type_="check")
    op.drop_constraint("ck_profiles_relationship_status", "profiles", type_="check")
    op.drop_constraint("ck_profiles_search_mode", "profiles", type_="check")
    op.execute(
        sa.text(
            "UPDATE profiles SET relationship_goal_code = 'unsure' "
            "WHERE relationship_goal_code IS NULL"
        )
    )
    op.alter_column("profiles", "relationship_goal_code", nullable=False)
    op.drop_column("profiles", "city_code")
    op.drop_column("profiles", "relationship_status")
    op.drop_column("profiles", "search_mode")
    op.create_check_constraint(
        "ck_profiles_goal",
        "profiles",
        "relationship_goal_code IN "
        "('serious_relationship','friends_with_benefits','unsure')",
    )
