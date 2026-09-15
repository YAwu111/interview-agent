"""drop unique document content_hash（去重改由上层按 (base_id, content_hash) 处理）

Revision ID: 9f8e7d6c5b4a
Revises: 1a2b3c4d5e6f
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9f8e7d6c5b4a"
down_revision: str | Sequence[str] | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=True)
