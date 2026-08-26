"""Allow in-transaction photo position parking for swaps.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_profile_photos_position", "profile_photos", type_="check")
    op.create_check_constraint(
        "ck_profile_photos_position",
        "profile_photos",
        "position BETWEEN -1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_profile_photos_position", "profile_photos", type_="check")
    op.create_check_constraint(
        "ck_profile_photos_position",
        "profile_photos",
        "position BETWEEN 0 AND 5",
    )
