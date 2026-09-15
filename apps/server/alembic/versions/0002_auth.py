"""auth tables"""
from alembic import op
import sqlalchemy as sa

revision = "0002_auth"
down_revision = "0001_record_phase1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("openid", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("families")
