"""add administrator-managed Host Completion rules

Revision ID: 0013_host_completion_manual_rules
Revises: 0012_reconciliation_proposals
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_host_completion_manual_rules"
down_revision = "0012_reconciliation_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host_completion_manual_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_prefix", sa.Text(), nullable=False),
        sa.Column("target_prefix", sa.Text(), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "prefix_length IN (16, 24)", name="ck_manual_rule_prefix_length"
        ),
        sa.UniqueConstraint(
            "source_prefix",
            "target_prefix",
            "prefix_length",
            name="uq_manual_rule_transformation",
        ),
    )


def downgrade() -> None:
    op.drop_table("host_completion_manual_rules")
