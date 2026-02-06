"""add_tag_color

Revision ID: 0006_add_tag_color
Revises: 0005_add_tags
Create Date: 2025-02-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_add_tag_color"
down_revision = "0005_add_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tags",
        sa.Column("color", sa.Text(), nullable=False, server_default=sa.text("'#e2e8f0'")),
    )


def downgrade() -> None:
    op.drop_column("tags", "color")
