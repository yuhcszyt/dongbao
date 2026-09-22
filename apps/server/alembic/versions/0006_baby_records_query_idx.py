"""baby_records: composite index for typed time-range queries (sleep/growth tools)"""
from alembic import op

revision = "0006_baby_records_query_idx"
down_revision = "0005_ai_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agent 按宝宝 + 类型 + 时间查睡眠/生长；软删行仍可走索引再过滤 deleted_at
    op.create_index(
        "ix_baby_records_baby_type_occurred",
        "baby_records",
        ["baby_id", "record_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_baby_records_baby_type_occurred", table_name="baby_records")
