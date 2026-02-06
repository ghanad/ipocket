"""add_tags

Revision ID: 0005_add_tags
Revises: 0004_add_ip_ranges
Create Date: 2025-02-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_add_tags"
down_revision = "0004_add_ip_ranges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "ip_asset_tags",
        sa.Column(
            "ip_asset_id",
            sa.Integer(),
            sa.ForeignKey("ip_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ip_asset_id", "tag_id"),
        sa.UniqueConstraint("ip_asset_id", "tag_id", name="uq_ip_asset_tags_asset_tag"),
    )


def downgrade() -> None:
    op.drop_table("ip_asset_tags")
    op.drop_table("tags")
