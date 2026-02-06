"""remove_subnet_gateway

Revision ID: 0002_remove_subnet_gateway
Revises: 0001_initial_schema
Create Date: 2024-11-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_remove_subnet_gateway"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ip_assets") as batch:
        batch.drop_column("subnet")
        batch.drop_column("gateway")


def downgrade() -> None:
    with op.batch_alter_table("ip_assets") as batch:
        batch.add_column(sa.Column("subnet", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("gateway", sa.Text(), nullable=False, server_default=""))
