"""Local prototype embeddings are DS Lab gte-base (768-d).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM profile_embeddings"))
    op.execute(sa.text("ALTER TABLE profile_embeddings DROP COLUMN embedding"))
    op.execute(
        sa.text(
            "ALTER TABLE profile_embeddings ADD COLUMN embedding vector(768) NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM profile_embeddings"))
    op.execute(sa.text("ALTER TABLE profile_embeddings DROP COLUMN embedding"))
    op.execute(
        sa.text(
            "ALTER TABLE profile_embeddings ADD COLUMN embedding vector(2560) NOT NULL"
        )
    )
