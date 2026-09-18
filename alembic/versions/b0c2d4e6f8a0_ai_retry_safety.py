"""Add bounded AI retry tracking.

Revision ID: b0c2d4e6f8a0
Revises: a9b1c3d5e7f9
Create Date: 2026-08-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c2d4e6f8a0"
down_revision: Union[str, Sequence[str], None] = "a9b1c3d5e7f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column(
            "ai_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("news", sa.Column("ai_last_error", sa.Text(), nullable=True))
    op.add_column(
        "news",
        sa.Column("ai_next_retry_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_news_ai_retry_queue",
        "news",
        ["ai_processed", "status", "ai_next_retry_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_ai_retry_queue", table_name="news")
    op.drop_column("news", "ai_next_retry_at")
    op.drop_column("news", "ai_last_error")
    op.drop_column("news", "ai_attempts")
