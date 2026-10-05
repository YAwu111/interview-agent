"""idempotency records 兜底表

Revision ID: a1b2c3d4e5f6
Revises: 9f8e7d6c5b4a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "9f8e7d6c5b4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_idempotency_records_key", "idempotency_records", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_key", table_name="idempotency_records")
    op.drop_table("idempotency_records")
