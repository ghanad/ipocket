"""add_ip_asset_listing_indexes

Revision ID: 0007_add_ip_asset_listing_indexes
Revises: 0006_add_tag_color
Create Date: 2026-02-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_add_ip_asset_listing_indexes"
down_revision = "0006_add_tag_color"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ip_assets_archived_project_type",
        "ip_assets",
        ["archived", "project_id", "type"],
    )
    op.create_index(
        "ix_ip_assets_archived_ip_address",
        "ip_assets",
        ["archived", "ip_address"],
    )
    op.create_index(
        "ix_ip_asset_tags_tag_id_ip_asset_id",
        "ip_asset_tags",
        ["tag_id", "ip_asset_id"],
    )
    op.create_index(
        "ix_tags_name_lower",
        "tags",
        [sa.text("lower(name)")],
    )


def downgrade() -> None:
    op.drop_index("ix_tags_name_lower", table_name="tags")
    op.drop_index("ix_ip_asset_tags_tag_id_ip_asset_id", table_name="ip_asset_tags")
    op.drop_index("ix_ip_assets_archived_ip_address", table_name="ip_assets")
    op.drop_index("ix_ip_assets_archived_project_type", table_name="ip_assets")
