"""Persist scoped cry results independently from short-lived audio."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0009_cry_history"
down_revision = "0008_private_cry_media"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("cry_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("baby_id", sa.Uuid(), sa.ForeignKey("babies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_id", sa.Uuid(), sa.ForeignKey("media_assets.id", ondelete="SET NULL"), unique=True),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("family_id", "baby_id", "created_at"):
        op.create_index(f"ix_cry_analyses_{column}", "cry_analyses", [column])


def downgrade():
    op.drop_table("cry_analyses")
