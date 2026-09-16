"""baby birth_date optional for soft onboarding"""
from alembic import op
import sqlalchemy as sa

revision = "0003_baby_birth_date_optional"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("babies", "birth_date", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE babies SET birth_date = CURRENT_DATE WHERE birth_date IS NULL")
    op.alter_column("babies", "birth_date", existing_type=sa.Date(), nullable=False)
