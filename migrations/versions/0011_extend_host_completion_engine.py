"""extend host completion decisions for unlinked asset review

Revision ID: 0011_extend_host_completion_engine
Revises: 0010_host_completion_decisions
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_extend_host_completion_engine"
down_revision = "0010_host_completion_decisions"
branch_labels = None
depends_on = None


_DECISIONS = (
    "decision IN ('ACCEPT', 'REJECT', 'CORRECTED', 'UNSURE', 'NO_BMC', "
    "'NO_OS', 'CREATE_HOST_ONLY', 'ATTACH_EXISTING', 'DEACTIVATE')"
)


def upgrade() -> None:
    # Batch mode recreates the table on SQLite, which also replaces the old
    # restrictive decision check and permits decisions without an existing Host.
    with op.batch_alter_table("host_completion_decisions") as batch_op:
        batch_op.add_column(sa.Column("case_type", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("os_address", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("bmc_address", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("target_host_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("host_name", sa.Text(), nullable=True))
        batch_op.alter_column("host_id", existing_type=sa.Integer(), nullable=True)
        batch_op.drop_constraint("ck_host_completion_decision", type_="check")
        batch_op.create_check_constraint("ck_host_completion_decision", _DECISIONS)
        batch_op.create_foreign_key(
            "fk_host_completion_decisions_target_host_id_hosts",
            "hosts",
            ["target_host_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        "UPDATE host_completion_decisions "
        "SET case_type = 'HOST_MISSING_BMC' WHERE case_type IS NULL"
    )
    with op.batch_alter_table("host_completion_decisions") as batch_op:
        batch_op.alter_column("case_type", existing_type=sa.Text(), nullable=False)
    with op.batch_alter_table("ip_assets") as batch_op:
        batch_op.alter_column("type", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("ip_assets") as batch_op:
        batch_op.alter_column("type", existing_type=sa.Text(), nullable=False)
    with op.batch_alter_table("host_completion_decisions") as batch_op:
        batch_op.drop_constraint(
            "fk_host_completion_decisions_target_host_id_hosts", type_="foreignkey"
        )
        batch_op.drop_constraint("ck_host_completion_decision", type_="check")
        batch_op.create_check_constraint(
            "ck_host_completion_decision",
            "decision IN ('ACCEPT', 'REJECT', 'CORRECTED', 'UNSURE', 'NO_BMC')",
        )
        batch_op.drop_column("host_name")
        batch_op.drop_column("target_host_id")
        batch_op.drop_column("bmc_address")
        batch_op.drop_column("os_address")
        batch_op.drop_column("case_type")
        batch_op.alter_column("host_id", existing_type=sa.Integer(), nullable=False)
