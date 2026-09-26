"""Private memory vectors remain scoped in Postgres."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_memory_vectors"
down_revision = "0010_family_sharing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_memories", sa.Column("embedding", postgresql.JSONB(), nullable=True))
    op.add_column("ai_memories", sa.Column("embedding_model", sa.String(64), nullable=True))
    op.add_column("ai_memories", sa.Column("embedding_content", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("ai_memories", "embedding_content")
    op.drop_column("ai_memories", "embedding_model")
    op.drop_column("ai_memories", "embedding")
