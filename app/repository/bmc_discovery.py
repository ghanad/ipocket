from __future__ import annotations

import sqlite3
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAssetType
from ._db import session_scope


def get_bmc_discovery_targets(
    connection_or_session: sqlite3.Connection | Session,
    host_ids: Optional[Sequence[int]] = None,
    only_unassigned: bool = True,
) -> list[dict[str, object]]:
    """Return hosts with active BMC IP assets that can be probed for vendor discovery."""

    with session_scope(connection_or_session) as session:
        statement = (
            select(
                db_schema.Host.id.label("host_id"),
                db_schema.Host.name.label("host_name"),
                db_schema.Vendor.name.label("vendor_name"),
                db_schema.IPAsset.id.label("asset_id"),
                db_schema.IPAsset.ip_address.label("ip_address"),
            )
            .select_from(db_schema.Host)
            .outerjoin(
                db_schema.Vendor, db_schema.Vendor.id == db_schema.Host.vendor_id
            )
            .join(
                db_schema.IPAsset,
                (db_schema.IPAsset.host_id == db_schema.Host.id)
                & (db_schema.IPAsset.archived == 0)
                & (db_schema.IPAsset.type == IPAssetType.BMC.value),
            )
            .order_by(db_schema.Host.id, db_schema.IPAsset.id)
        )

        if only_unassigned:
            statement = statement.where(db_schema.Host.vendor_id.is_(None))

        if host_ids:
            statement = statement.where(db_schema.Host.id.in_(list(host_ids)))

        rows = session.execute(statement).mappings().all()

    # Group by host_id
    hosts_map: dict[int, dict[str, object]] = {}
    for row in rows:
        hid = int(row["host_id"])
        if hid not in hosts_map:
            hosts_map[hid] = {
                "host_id": hid,
                "host_name": str(row["host_name"]),
                "vendor_name": row["vendor_name"],
                "bmc_assets": [],
            }
        hosts_map[hid]["bmc_assets"].append(
            {
                "id": int(row["asset_id"]),
                "ip_address": str(row["ip_address"]),
            }
        )

    return list(hosts_map.values())
