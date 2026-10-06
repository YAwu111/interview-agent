"""usage_daily 用量日聚合表

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("latency_sum_ms", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "model", "date", name="uq_usage_daily_user_model_date"),
    )
    op.create_index("ix_usage_daily_user_id", "usage_daily", ["user_id"])
    op.create_index("ix_usage_daily_model", "usage_daily", ["model"])


def downgrade() -> None:
    op.drop_index("ix_usage_daily_model", table_name="usage_daily")
    op.drop_index("ix_usage_daily_user_id", table_name="usage_daily")
    op.drop_table("usage_daily")
