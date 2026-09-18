"""Sprint 15.1 OEM sources

Revision ID: 6c80ce7244d6
Revises: 35240ecfe6d2
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c80ce7244d6"
down_revision: Union[str, Sequence[str], None] = "35240ecfe6d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source_type
    op.add_column(
        "sources",
        sa.Column(
            "source_type",
            sa.String(length=30),
            nullable=False,
            server_default="editorial",
        ),
    )

    # brand
    op.add_column(
        "sources",
        sa.Column(
            "brand",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # is_oem
    op.add_column(
        "sources",
        sa.Column(
            "is_oem",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sources", "is_oem")
    op.drop_column("sources", "brand")
    op.drop_column("sources", "source_type")