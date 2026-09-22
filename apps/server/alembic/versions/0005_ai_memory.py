"""ai_memories: long-term baby-scoped notes (not Record, not RAG)"""
from alembic import op
import sqlalchemy as sa

revision = "0005_ai_memory"
down_revision = "0004_ai_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("baby_id", sa.Uuid(), sa.ForeignKey("babies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_memories_family_id", "ai_memories", ["family_id"])
    op.create_index("ix_ai_memories_baby_id", "ai_memories", ["baby_id"])


def downgrade() -> None:
    op.drop_table("ai_memories")
