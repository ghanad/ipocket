from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import Host, IPAsset, IPAssetType
from app.utils import DEFAULT_PROJECT_COLOR
from .mappers import _ip_address_sort_key, _row_to_host, _row_to_ip_asset


def _resolve_vendor_id(connection: sqlite3.Connection, vendor_name: Optional[str]) -> Optional[int]:
    if vendor_name is None:
        return None
    row = connection.execute("SELECT id FROM vendors WHERE name = ?", (vendor_name,)).fetchone()
    if row is None:
        raise sqlite3.IntegrityError("Vendor name does not exist.")
    return int(row["id"])


def create_host(connection: sqlite3.Connection, name: str, notes: Optional[str] = None, vendor: Optional[str] = None) -> Host:
    cursor = connection.execute("INSERT INTO hosts (name, notes, vendor_id) VALUES (?, ?, ?)", (name, notes, _resolve_vendor_id(connection, vendor)))
    connection.commit()
    return Host(id=cursor.lastrowid, name=name, notes=notes, vendor=vendor)



def list_hosts(connection: sqlite3.Connection) -> Iterable[Host]:
    rows = connection.execute("SELECT hosts.id, hosts.name, hosts.notes, vendors.name AS vendor_name FROM hosts LEFT JOIN vendors ON vendors.id = hosts.vendor_id ORDER BY hosts.name").fetchall()
    return [_row_to_host(row) for row in rows]



def get_host_by_id(connection: sqlite3.Connection, host_id: int) -> Optional[Host]:
    row = connection.execute("SELECT hosts.id, hosts.name, hosts.notes, vendors.name AS vendor_name FROM hosts LEFT JOIN vendors ON vendors.id = hosts.vendor_id WHERE hosts.id = ?", (host_id,)).fetchone()
    return _row_to_host(row) if row else None



def get_host_by_name(connection: sqlite3.Connection, name: str) -> Optional[Host]:
    row = connection.execute("SELECT hosts.id, hosts.name, hosts.notes, vendors.name AS vendor_name FROM hosts LEFT JOIN vendors ON vendors.id = hosts.vendor_id WHERE hosts.name = ?", (name,)).fetchone()
    return _row_to_host(row) if row else None



def list_hosts_with_ip_counts(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT
            hosts.id AS id,
            hosts.name AS name,
            hosts.notes AS notes,
            vendors.name AS vendor,
            (
                SELECT COUNT(DISTINCT ip_assets.project_id)
                FROM ip_assets
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
            ) AS project_count,
            (
                SELECT projects.name
                FROM ip_assets
                JOIN projects ON projects.id = ip_assets.project_id
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
                ORDER BY projects.name
                LIMIT 1
            ) AS project_name,
            (
                SELECT projects.color
                FROM ip_assets
                JOIN projects ON projects.id = ip_assets.project_id
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
                ORDER BY projects.name
                LIMIT 1
            ) AS project_color,
            (
                SELECT COUNT(*)
                FROM ip_assets
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
            ) AS ip_count,
            (
                SELECT group_concat(ip_address, ', ')
                FROM (
                    SELECT ip_address
                    FROM ip_assets
                    WHERE host_id = hosts.id
                      AND archived = 0
                      AND type = 'OS'
                    ORDER BY ip_address
                )
            ) AS os_ips,
            (
                SELECT group_concat(ip_address, ', ')
                FROM (
                    SELECT ip_address
                    FROM ip_assets
                    WHERE host_id = hosts.id
                      AND archived = 0
                      AND type = 'BMC'
                    ORDER BY ip_address
                )
            ) AS bmc_ips
        FROM hosts
        LEFT JOIN vendors ON vendors.id = hosts.vendor_id
        ORDER BY hosts.name
        """
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "notes": row["notes"],
            "vendor": row["vendor"],
            "project_count": int(row["project_count"] or 0),
            "project_name": row["project_name"] or "",
            "project_color": row["project_color"] or "",
            "ip_count": int(row["ip_count"] or 0),
            "os_ips": row["os_ips"] or "",
            "bmc_ips": row["bmc_ips"] or "",
        }
        for row in rows
    ]



def count_hosts(connection: sqlite3.Connection) -> int:
    """Return the total number of hosts."""
    row = connection.execute("SELECT COUNT(*) AS count FROM hosts").fetchone()
    return row["count"] if row else 0



def list_hosts_with_ip_counts_paginated(
    connection: sqlite3.Connection,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    """Return a paginated list of hosts with IP counts."""
    rows = connection.execute(
        """
        SELECT
            hosts.id AS id,
            hosts.name AS name,
            hosts.notes AS notes,
            vendors.name AS vendor,
            (
                SELECT COUNT(DISTINCT ip_assets.project_id)
                FROM ip_assets
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
            ) AS project_count,
            (
                SELECT projects.name
                FROM ip_assets
                JOIN projects ON projects.id = ip_assets.project_id
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
                ORDER BY projects.name
                LIMIT 1
            ) AS project_name,
            (
                SELECT projects.color
                FROM ip_assets
                JOIN projects ON projects.id = ip_assets.project_id
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
                  AND ip_assets.project_id IS NOT NULL
                ORDER BY projects.name
                LIMIT 1
            ) AS project_color,
            (
                SELECT COUNT(*)
                FROM ip_assets
                WHERE ip_assets.host_id = hosts.id
                  AND ip_assets.archived = 0
            ) AS ip_count,
            (
                SELECT group_concat(ip_address, ', ')
                FROM (
                    SELECT ip_address
                    FROM ip_assets
                    WHERE host_id = hosts.id
                      AND archived = 0
                      AND type = 'OS'
                    ORDER BY ip_address
                )
            ) AS os_ips,
            (
                SELECT group_concat(ip_address, ', ')
                FROM (
                    SELECT ip_address
                    FROM ip_assets
                    WHERE host_id = hosts.id
                      AND archived = 0
                      AND type = 'BMC'
                    ORDER BY ip_address
                )
            ) AS bmc_ips
        FROM hosts
        LEFT JOIN vendors ON vendors.id = hosts.vendor_id
        ORDER BY hosts.name
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "notes": row["notes"],
            "vendor": row["vendor"],
            "project_count": int(row["project_count"] or 0),
            "project_name": row["project_name"] or "",
            "project_color": row["project_color"] or "",
            "ip_count": int(row["ip_count"] or 0),
            "os_ips": row["os_ips"] or "",
            "bmc_ips": row["bmc_ips"] or "",
        }
        for row in rows
    ]



def get_host_linked_assets_grouped(connection: sqlite3.Connection, host_id: int) -> dict[str, list[IPAsset]]:
    rows = connection.execute("SELECT * FROM ip_assets WHERE host_id = ? AND archived = 0 ORDER BY ip_address", (host_id,)).fetchall()
    assets = [_row_to_ip_asset(row) for row in rows]
    return {
        "os": [a for a in assets if a.asset_type == IPAssetType.OS],
        "bmc": [a for a in assets if a.asset_type == IPAssetType.BMC],
        "other": [a for a in assets if a.asset_type not in (IPAssetType.OS, IPAssetType.BMC)],
    }



def list_host_pair_ips_for_hosts(
    connection: sqlite3.Connection,
    host_ids: Iterable[int],
) -> dict[int, dict[str, list[str]]]:
    host_ids_list = sorted({host_id for host_id in host_ids if host_id is not None})
    if not host_ids_list:
        return {}
    placeholders = ",".join(["?"] * len(host_ids_list))
    rows = connection.execute(
        f"""
        SELECT host_id, type, ip_address
        FROM ip_assets
        WHERE archived = 0
          AND host_id IN ({placeholders})
          AND type IN ('OS', 'BMC')
        ORDER BY host_id, type, ip_address
        """,
        host_ids_list,
    ).fetchall()
    mapping: dict[int, dict[str, list[str]]] = {
        host_id: {"OS": [], "BMC": []} for host_id in host_ids_list
    }
    for row in rows:
        mapping.setdefault(row["host_id"], {"OS": [], "BMC": []})[row["type"]].append(row["ip_address"])
    return mapping



def update_host(connection: sqlite3.Connection, host_id: int, name: Optional[str] = None, notes: Optional[str] = None, vendor: Optional[str] = None) -> Optional[Host]:
    connection.execute(
        "UPDATE hosts SET name = COALESCE(?, name), notes = COALESCE(?, notes), vendor_id = COALESCE(?, vendor_id), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, notes, _resolve_vendor_id(connection, vendor), host_id),
    )
    connection.commit()
    return get_host_by_id(connection, host_id)



def delete_host(connection: sqlite3.Connection, host_id: int) -> bool:
    connection.execute(
        "UPDATE ip_assets SET host_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE host_id = ?",
        (host_id,),
    )
    cursor = connection.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
    connection.commit()
    return cursor.rowcount > 0
