"""Persist quick capture conversation, retries and follow-up context."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_quick_capture"
down_revision = "0006_baby_records_query_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("record_drafts", sa.Column("capture_context", postgresql.JSONB(), nullable=True))
    op.create_index("uq_quick_capture_media", "record_drafts", ["media_id"], unique=True,
                    postgresql_where=sa.text("capture_context IS NOT NULL"))


def downgrade():
    op.drop_index("uq_quick_capture_media", table_name="record_drafts")
    op.drop_column("record_drafts", "capture_context")
