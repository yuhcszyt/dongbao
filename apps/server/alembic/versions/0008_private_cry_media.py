"""Keep cry-analysis audio private and expire it after seven days."""
from alembic import op
import sqlalchemy as sa

revision = "0008_private_cry_media"
down_revision = "0007_quick_capture"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("media_assets", sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("media_assets", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_media_assets_expires_at", "media_assets", ["expires_at"])


def downgrade():
    op.drop_index("ix_media_assets_expires_at", table_name="media_assets")
    op.drop_column("media_assets", "expires_at")
    op.drop_column("media_assets", "is_private")
