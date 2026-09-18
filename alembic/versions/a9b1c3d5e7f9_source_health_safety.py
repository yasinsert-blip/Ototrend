"""Add consecutive source failure tracking.

Revision ID: a9b1c3d5e7f9
Revises: 6c80ce7244d6
Create Date: 2026-08-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9b1c3d5e7f9"
down_revision: Union[str, Sequence[str], None] = "6c80ce7244d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("sources", sa.Column("auto_disabled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "auto_disabled_at")
    op.drop_column("sources", "consecutive_failures")
