"""record phase 1 schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_record_phase1"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "babies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("nickname", sa.String(30), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("baby_id", sa.Uuid(), sa.ForeignKey("babies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "record_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("baby_id", sa.Uuid(), sa.ForeignKey("babies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("media_id", sa.Uuid(), sa.ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("record_type", sa.String(32), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("recognition_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "baby_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("baby_id", sa.Uuid(), sa.ForeignKey("babies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("record_type", sa.String(32), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, index=True),
    )
    op.create_table(
        "record_media",
        sa.Column("record_id", sa.Uuid(), sa.ForeignKey("baby_records.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("media_id", sa.Uuid(), sa.ForeignKey("media_assets.id", ondelete="RESTRICT"), primary_key=True),
    )

def downgrade() -> None:
    op.drop_table("record_media")
    op.drop_table("baby_records")
    op.drop_table("record_drafts")
    op.drop_table("media_assets")
    op.drop_table("babies")

