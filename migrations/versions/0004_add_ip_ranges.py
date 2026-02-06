"""add_ip_ranges

Revision ID: 0004_add_ip_ranges
Revises: 0003_add_audit_logs
Create Date: 2025-02-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_add_ip_ranges"
down_revision = "0003_add_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_ranges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cidr", sa.Text(), nullable=False, unique=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("ip_ranges")
