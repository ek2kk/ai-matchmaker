"""Profile embeddings for retrieval.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(sa.text("DROP TABLE IF EXISTS profile_embeddings"))
    op.create_table(
        "profile_embeddings",
        sa.Column("embedding_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("projection_schema_version", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('self','desired_partner')", name="ck_embed_kind"),
        sa.CheckConstraint("source_version > 0", name="ck_embed_source_version"),
        sa.UniqueConstraint(
            "profile_id",
            "kind",
            "source_version",
            "model_version",
            name="uq_profile_embeddings_cache",
        ),
    )
    op.execute(
        sa.text(
            "ALTER TABLE profile_embeddings "
            "ALTER COLUMN embedding TYPE vector(2560) "
            "USING embedding::vector(2560)"
        )
    )
    op.create_index(
        "ix_profile_embeddings_profile_kind",
        "profile_embeddings",
        ["profile_id", "kind"],
    )
    # ponytail: pgvector HNSW rejects >2000 dims; EmbeddingsGigaR is 2560.
    # Retrieval in task 8 uses exact cosine or halfvec until the index limit moves.


def downgrade() -> None:
    op.drop_index("ix_profile_embeddings_profile_kind", table_name="profile_embeddings")
    op.drop_table("profile_embeddings")
