"""add_host_completion_decisions

Revision ID: 0010_host_completion_decisions
Revises: 0009_add_ip_int_column
Create Date: 2026-08-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_host_completion_decisions"
down_revision = "0009_add_ip_int_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host_completion_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("candidate_ip", sa.Text(), nullable=True),
        sa.Column("corrected_ip", sa.Text(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.Text(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "mode IN ('SUGGEST', 'ASK')", name="ck_host_completion_mode"
        ),
        sa.CheckConstraint(
            "decision IN ('ACCEPT', 'REJECT', 'CORRECTED', 'UNSURE', 'NO_BMC')",
            name="ck_host_completion_decision",
        ),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_host_completion_decisions_host_decision",
        "host_completion_decisions",
        ["host_id", "decision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_host_completion_decisions_host_decision",
        table_name="host_completion_decisions",
    )
    op.drop_table("host_completion_decisions")
