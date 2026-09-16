"""0001: create system_info (migration probe table)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_create_system_info"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_info",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_info")
