"""m3_rag

Revision ID: 8fa9f3ea26c8
Revises: 13500510252a
Create Date: 2026-06-15 12:30:55.478183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8fa9f3ea26c8'
down_revision: Union[str, None] = '13500510252a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE documents ADD COLUMN embedding vector(1536)")

    op.add_column("scenarios", sa.Column("sources", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenarios", "sources")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
