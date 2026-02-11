from __future__ import annotations

import ipaddress
import sqlite3
from typing import Iterable, Optional

from app.models import IPAssetType, IPRange
from app.utils import DEFAULT_PROJECT_COLOR, normalize_cidr, parse_ipv4_network
from .assets import list_tag_details_for_ip_assets
from .hosts import list_host_pair_ips_for_hosts
from .mappers import _row_to_ip_range


def create_ip_range(
    connection: sqlite3.Connection,
    name: str,
    cidr: str,
    notes: Optional[str] = None,
) -> IPRange:
    normalized_cidr = normalize_cidr(cidr)
    cursor = connection.execute(
        "INSERT INTO ip_ranges (name, cidr, notes) VALUES (?, ?, ?)",
        (name, normalized_cidr, notes),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM ip_ranges WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created IP range.")
    return _row_to_ip_range(row)


def list_ip_ranges(connection: sqlite3.Connection) -> Iterable[IPRange]:
    rows = connection.execute("SELECT * FROM ip_ranges ORDER BY name").fetchall()
    return [_row_to_ip_range(row) for row in rows]


def get_ip_range_by_id(connection: sqlite3.Connection, range_id: int) -> IPRange | None:
    row = connection.execute(
        "SELECT * FROM ip_ranges WHERE id = ?", (range_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_ip_range(row)


def update_ip_range(
    connection: sqlite3.Connection,
    range_id: int,
    name: str,
    cidr: str,
    notes: Optional[str] = None,
) -> IPRange | None:
    normalized_cidr = normalize_cidr(cidr)
    connection.execute(
        "UPDATE ip_ranges SET name = ?, cidr = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, normalized_cidr, notes, range_id),
    )
    connection.commit()
    return get_ip_range_by_id(connection, range_id)


def delete_ip_range(connection: sqlite3.Connection, range_id: int) -> bool:
    cursor = connection.execute("DELETE FROM ip_ranges WHERE id = ?", (range_id,))
    connection.commit()
    return cursor.rowcount > 0


def _total_usable_addresses(network: ipaddress.IPv4Network) -> int:
    if network.prefixlen == 32:
        return 1
    if network.prefixlen == 31:
        return 2
    return max(int(network.num_addresses) - 2, 0)


def get_ip_range_utilization(connection: sqlite3.Connection) -> list[dict[str, object]]:
    ranges = list(list_ip_ranges(connection))
    rows = connection.execute(
        "SELECT DISTINCT ip_address FROM ip_assets WHERE archived = 0"
    ).fetchall()
    ip_addresses: set[ipaddress.IPv4Address] = set()
    for row in rows:
        try:
            ip_value = ipaddress.ip_address(row["ip_address"])
        except ValueError:
            continue
        if ip_value.version == 4:
            ip_addresses.add(ip_value)

    utilization: list[dict[str, object]] = []
    for ip_range in ranges:
        network = parse_ipv4_network(ip_range.cidr)
        total = int(network.num_addresses)
        total_usable = _total_usable_addresses(network)
        used = sum(1 for ip_value in ip_addresses if ip_value in network)
        free = max(total_usable - used, 0)
        utilization_percent = (used / total_usable * 100.0) if total_usable else 0.0
        utilization.append(
            {
                "id": ip_range.id,
                "name": ip_range.name,
                "cidr": ip_range.cidr,
                "notes": ip_range.notes,
                "total": total,
                "total_usable": total_usable,
                "used": used,
                "free": free,
                "utilization_percent": utilization_percent,
            }
        )
    return utilization


def get_ip_range_address_breakdown(
    connection: sqlite3.Connection,
    range_id: int,
) -> dict[str, object] | None:
    ip_range = get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        return None

    network = parse_ipv4_network(ip_range.cidr)
    rows = connection.execute(
        """
        SELECT ip_assets.id AS asset_id,
               ip_assets.ip_address AS ip_address,
               ip_assets.type AS asset_type,
               ip_assets.host_id AS host_id,
               ip_assets.project_id AS project_id,
               ip_assets.notes AS notes,
               projects.name AS project_name,
               projects.color AS project_color
        FROM ip_assets
        LEFT JOIN projects ON projects.id = ip_assets.project_id
        WHERE ip_assets.archived = 0
        """
    ).fetchall()
    used_entries: list[dict[str, object]] = []
    used_addresses: set[ipaddress.IPv4Address] = set()
    used_asset_ids: list[int] = []
    used_host_ids: list[int] = []
    for row in rows:
        try:
            ip_value = ipaddress.ip_address(row["ip_address"])
        except ValueError:
            continue
        if ip_value.version != 4 or ip_value not in network:
            continue
        used_addresses.add(ip_value)
        used_asset_ids.append(row["asset_id"])
        if row["host_id"]:
            used_host_ids.append(row["host_id"])
        used_entries.append(
            {
                "ip_address": str(ip_value),
                "status": "used",
                "asset_id": row["asset_id"],
                "host_id": row["host_id"],
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "project_color": row["project_color"] or DEFAULT_PROJECT_COLOR,
                "project_unassigned": not row["project_name"],
                "asset_type": row["asset_type"],
                "notes": row["notes"] or "",
                "host_pair": "",
                "tags": [],
            }
        )

    tag_map = list_tag_details_for_ip_assets(connection, used_asset_ids)
    for entry in used_entries:
        entry["tags"] = tag_map.get(entry["asset_id"], [])
    host_pair_lookup = list_host_pair_ips_for_hosts(connection, used_host_ids)
    for entry in used_entries:
        host_id = entry.get("host_id")
        asset_type = entry.get("asset_type")
        if host_id and asset_type in (IPAssetType.OS.value, IPAssetType.BMC.value):
            pair_type = (
                IPAssetType.BMC.value
                if asset_type == IPAssetType.OS.value
                else IPAssetType.OS.value
            )
            entry["host_pair"] = ", ".join(
                host_pair_lookup.get(host_id, {}).get(pair_type, [])
            )

    used_sorted = sorted(
        used_entries, key=lambda entry: int(ipaddress.ip_address(entry["ip_address"]))
    )
    usable_addresses = list(network.hosts())
    free_entries = [
        {
            "ip_address": str(ip_value),
            "status": "free",
            "asset_id": None,
            "project_id": None,
            "project_name": None,
            "project_color": DEFAULT_PROJECT_COLOR,
            "project_unassigned": True,
            "asset_type": None,
            "notes": "",
            "host_pair": "",
            "tags": [],
        }
        for ip_value in usable_addresses
        if ip_value not in used_addresses
    ]
    address_entries = sorted(
        [*used_sorted, *free_entries],
        key=lambda entry: int(ipaddress.ip_address(entry["ip_address"])),
    )

    return {
        "ip_range": ip_range,
        "addresses": address_entries,
        "used": len(used_sorted),
        "free": len(free_entries),
        "total_usable": len(usable_addresses),
    }
