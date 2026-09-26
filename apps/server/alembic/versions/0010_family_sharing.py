"""Family membership, single-use invites and audit history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0010_family_sharing"
down_revision = "0009_cry_history"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("families", sa.Column("name", sa.String(40), nullable=False, server_default="我的家庭"))
    op.add_column("users", sa.Column("display_name", sa.String(30), nullable=False, server_default="家人"))
    op.create_table("family_members",
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_family_role"))
    op.execute("INSERT INTO family_members (family_id,user_id,role,joined_at) SELECT family_id,id,CASE WHEN row_number() OVER (PARTITION BY family_id ORDER BY created_at,id)=1 THEN 'owner' ELSE 'member' END,created_at FROM users")
    op.create_table("family_invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_family_invites_family_id", "family_invites", ["family_id"])
    op.create_table("family_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid()), sa.Column("target_id", sa.Uuid()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_family_audits_family_id", "family_audits", ["family_id"])


def downgrade():
    op.drop_table("family_audits")
    op.drop_table("family_invites")
    op.drop_table("family_members")
    op.drop_column("users", "display_name")
    op.drop_column("families", "name")
