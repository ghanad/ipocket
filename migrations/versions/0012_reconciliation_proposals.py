"""add proposal safety and idempotency to host reconciliation decisions

Revision ID: 0012_reconciliation_proposals
Revises: 0011_extend_host_completion_engine
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_reconciliation_proposals"
down_revision = "0011_extend_host_completion_engine"
branch_labels = None
depends_on = None


_DECISIONS = (
    "decision IN ('ACCEPT', 'REJECT', 'CORRECTED', 'CORRECT', 'WRONG_PAIR', "
    "'UNSURE', 'EXCEPTION', 'NO_BMC', 'NO_OS', 'CREATE_HOST_ONLY', "
    "'ATTACH_EXISTING', 'DEACTIVATE')"
)


def upgrade() -> None:
    with op.batch_alter_table("host_completion_decisions") as batch_op:
        batch_op.add_column(sa.Column("proposal_id", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("inventory_fingerprint", sa.Text(), nullable=True)
        )
        batch_op.add_column(sa.Column("idempotency_key", sa.Text(), nullable=True))
        batch_op.drop_constraint("ck_host_completion_decision", type_="check")
        batch_op.create_check_constraint("ck_host_completion_decision", _DECISIONS)
        batch_op.create_unique_constraint(
            "uq_host_completion_decisions_idempotency_key", ["idempotency_key"]
        )
    op.create_index(
        "ix_host_completion_decisions_proposal_id",
        "host_completion_decisions",
        ["proposal_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_host_completion_decisions_proposal_id",
        table_name="host_completion_decisions",
    )
    with op.batch_alter_table("host_completion_decisions") as batch_op:
        batch_op.drop_constraint(
            "uq_host_completion_decisions_idempotency_key", type_="unique"
        )
        batch_op.drop_constraint("ck_host_completion_decision", type_="check")
        batch_op.create_check_constraint(
            "ck_host_completion_decision",
            "decision IN ('ACCEPT', 'REJECT', 'CORRECTED', 'UNSURE', 'NO_BMC', "
            "'NO_OS', 'CREATE_HOST_ONLY', 'ATTACH_EXISTING', 'DEACTIVATE')",
        )
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("inventory_fingerprint")
        batch_op.drop_column("proposal_id")
