"""add_ip_int_column

Revision ID: 0009_add_ip_int_column
Revises: 0008_add_sessions
Create Date: 2026-02-20 00:00:00.000000
"""

from __future__ import annotations

import ipaddress

from alembic import op
import sqlalchemy as sa

revision = "0009_add_ip_int_column"
down_revision = "0008_add_sessions"
branch_labels = None
depends_on = None


def _ipv4_to_int(value: str) -> int | None:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        parts = value.split(".")
        if len(parts) != 4 or not all(part.isdigit() for part in parts):
            return None
        octets = [int(part) for part in parts]
        if not all(0 <= octet <= 255 for octet in octets):
            return None
        return (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
    if parsed.version != 4:
        return None
    return int(parsed)


def upgrade() -> None:
    with op.batch_alter_table("ip_assets") as batch_op:
        batch_op.add_column(sa.Column("ip_int", sa.Integer(), nullable=True))

    bind = op.get_bind()
    rows = (
        bind.execute(sa.text("SELECT id, ip_address FROM ip_assets")).mappings().all()
    )
    for row in rows:
        ip_int = _ipv4_to_int(str(row["ip_address"] or ""))
        bind.execute(
            sa.text("UPDATE ip_assets SET ip_int = :ip_int WHERE id = :id"),
            {"ip_int": ip_int, "id": int(row["id"])},
        )

    op.create_index(
        "ix_ip_assets_archived_ip_int",
        "ip_assets",
        ["archived", "ip_int"],
    )


def downgrade() -> None:
    op.drop_index("ix_ip_assets_archived_ip_int", table_name="ip_assets")
    with op.batch_alter_table("ip_assets") as batch_op:
        batch_op.drop_column("ip_int")
