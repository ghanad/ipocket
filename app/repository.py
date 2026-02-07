from __future__ import annotations

import ipaddress
import sqlite3
from typing import Iterable, Optional

from app.models import AuditLog, Host, IPAsset, IPAssetType, IPRange, Project, Tag, User, UserRole, Vendor
from app.utils import (
    DEFAULT_PROJECT_COLOR,
    DEFAULT_TAG_COLOR,
    normalize_cidr,
    normalize_hex_color,
    normalize_tag_names,
    parse_ipv4_network,
)


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
    )


def _row_to_host(row: sqlite3.Row) -> Host:
    return Host(id=row["id"], name=row["name"], notes=row["notes"], vendor=row["vendor_name"])


def _row_to_vendor(row: sqlite3.Row) -> Vendor:
    return Vendor(id=row["id"], name=row["name"])


def _row_to_tag(row: sqlite3.Row) -> Tag:
    return Tag(id=row["id"], name=row["name"], color=row["color"])


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        hashed_password=row["hashed_password"],
        role=UserRole(row["role"]),
        is_active=bool(row["is_active"]),
    )


def _row_to_ip_asset(row: sqlite3.Row) -> IPAsset:
    return IPAsset(
        id=row["id"],
        ip_address=row["ip_address"],
        asset_type=IPAssetType(row["type"]),
        project_id=row["project_id"],
        host_id=row["host_id"],
        notes=row["notes"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_audit_log(row: sqlite3.Row) -> AuditLog:
    return AuditLog(
        id=row["id"],
        user_id=row["user_id"],
        username=row["username"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        target_label=row["target_label"],
        action=row["action"],
        changes=row["changes"],
        created_at=row["created_at"],
    )


def _row_to_ip_range(row: sqlite3.Row) -> IPRange:
    return IPRange(
        id=row["id"],
        name=row["name"],
        cidr=row["cidr"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_audit_log(
    connection: sqlite3.Connection,
    user: Optional[User],
    action: str,
    target_type: str,
    target_id: int,
    target_label: str,
    changes: Optional[str] = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (
            user_id,
            username,
            target_type,
            target_id,
            target_label,
            action,
            changes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.id if user else None,
            user.username if user else None,
            target_type,
            target_id,
            target_label,
            action,
            changes,
        ),
    )


def get_audit_logs_for_ip(connection: sqlite3.Connection, ip_asset_id: int) -> list[AuditLog]:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_logs
        WHERE target_type = 'IP_ASSET'
          AND target_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (ip_asset_id,),
    ).fetchall()
    return [_row_to_audit_log(row) for row in rows]


def list_audit_logs(
    connection: sqlite3.Connection,
    target_type: str = "IP_ASSET",
    limit: int = 200,
) -> list[AuditLog]:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_logs
        WHERE target_type = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (target_type, limit),
    ).fetchall()
    return [_row_to_audit_log(row) for row in rows]


def _project_label(connection: sqlite3.Connection, project_id: Optional[int]) -> str:
    if project_id is None:
        return "Unassigned"
    project = connection.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        return f"Unknown ({project_id})"
    return project["name"]


def _host_label(connection: sqlite3.Connection, host_id: Optional[int]) -> str:
    if host_id is None:
        return "Unassigned"
    host = connection.execute("SELECT name FROM hosts WHERE id = ?", (host_id,)).fetchone()
    if host is None:
        return f"Unknown ({host_id})"
    return host["name"]


def _summarize_ip_asset_changes(connection: sqlite3.Connection, existing: IPAsset, updated: IPAsset) -> str:
    changes: list[str] = []
    if existing.asset_type != updated.asset_type:
        changes.append(f"type: {existing.asset_type.value} -> {updated.asset_type.value}")
    if existing.project_id != updated.project_id:
        changes.append(
            f"project: {_project_label(connection, existing.project_id)} -> {_project_label(connection, updated.project_id)}"
        )
    if existing.host_id != updated.host_id:
        changes.append(
            f"host: {_host_label(connection, existing.host_id)} -> {_host_label(connection, updated.host_id)}"
        )
    if (existing.notes or "") != (updated.notes or ""):
        changes.append(f"notes: {existing.notes or ''} -> {updated.notes or ''}")
    return "; ".join(changes) if changes else "No changes recorded."


def create_project(
    connection: sqlite3.Connection,
    name: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> Project:
    normalized_color = color or DEFAULT_PROJECT_COLOR
    cursor = connection.execute(
        "INSERT INTO projects (name, description, color) VALUES (?, ?, ?)",
        (name, description, normalized_color),
    )
    connection.commit()
    return Project(id=cursor.lastrowid, name=name, description=description, color=normalized_color)


def get_project_by_id(connection: sqlite3.Connection, project_id: int) -> Optional[Project]:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def update_project(
    connection: sqlite3.Connection,
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[Project]:
    connection.execute(
        """
        UPDATE projects
        SET name = COALESCE(?, name),
            description = COALESCE(?, description),
            color = COALESCE(?, color)
        WHERE id = ?
        """,
        (name, description, color, project_id),
    )
    connection.commit()
    row = connection.execute("SELECT id, name, description, color FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def list_projects(connection: sqlite3.Connection) -> Iterable[Project]:
    rows = connection.execute("SELECT id, name, description, color FROM projects ORDER BY name").fetchall()
    return [_row_to_project(row) for row in rows]


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
    row = connection.execute("SELECT * FROM ip_ranges WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created IP range.")
    return _row_to_ip_range(row)


def list_ip_ranges(connection: sqlite3.Connection) -> Iterable[IPRange]:
    rows = connection.execute("SELECT * FROM ip_ranges ORDER BY name").fetchall()
    return [_row_to_ip_range(row) for row in rows]


def get_ip_range_by_id(connection: sqlite3.Connection, range_id: int) -> IPRange | None:
    row = connection.execute("SELECT * FROM ip_ranges WHERE id = ?", (range_id,)).fetchone()
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
            pair_type = IPAssetType.BMC.value if asset_type == IPAssetType.OS.value else IPAssetType.OS.value
            entry["host_pair"] = ", ".join(host_pair_lookup.get(host_id, {}).get(pair_type, []))

    used_sorted = sorted(used_entries, key=lambda entry: int(ipaddress.ip_address(entry["ip_address"])))
    usable_addresses = list(network.hosts())
    free_entries = [
        {
            "ip_address": str(ip_value),
            "status": "free",
            "asset_id": None,
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


def create_user(connection: sqlite3.Connection, username: str, hashed_password: str, role: UserRole, is_active: bool = True) -> User:
    cursor = connection.execute(
        "INSERT INTO users (username, hashed_password, role, is_active) VALUES (?, ?, ?, ?)",
        (username, hashed_password, role.value, int(is_active)),
    )
    connection.commit()
    row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created user.")
    return _row_to_user(row)


def count_users(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return int(row["total"] or 0) if row else 0


def get_management_summary(connection: sqlite3.Connection) -> dict[str, int]:
    active_ip_row = connection.execute(
        "SELECT COUNT(*) AS total FROM ip_assets WHERE archived = 0"
    ).fetchone()
    archived_ip_row = connection.execute(
        "SELECT COUNT(*) AS total FROM ip_assets WHERE archived = 1"
    ).fetchone()
    host_row = connection.execute("SELECT COUNT(*) AS total FROM hosts").fetchone()
    vendor_row = connection.execute("SELECT COUNT(*) AS total FROM vendors").fetchone()
    project_row = connection.execute("SELECT COUNT(*) AS total FROM projects").fetchone()
    return {
        "active_ip_total": int(active_ip_row["total"] or 0) if active_ip_row else 0,
        "archived_ip_total": int(archived_ip_row["total"] or 0) if archived_ip_row else 0,
        "host_total": int(host_row["total"] or 0) if host_row else 0,
        "vendor_total": int(vendor_row["total"] or 0) if vendor_row else 0,
        "project_total": int(project_row["total"] or 0) if project_row else 0,
    }


def get_user_by_username(connection: sqlite3.Connection, username: str) -> Optional[User]:
    row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> Optional[User]:
    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None




def _resolve_vendor_id(connection: sqlite3.Connection, vendor_name: Optional[str]) -> Optional[int]:
    if vendor_name is None:
        return None
    vendor = get_vendor_by_name(connection, vendor_name)
    if vendor is None:
        raise sqlite3.IntegrityError("Vendor name does not exist.")
    return vendor.id

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
    linked_count_row = connection.execute(
        "SELECT COUNT(*) AS linked_count FROM ip_assets WHERE host_id = ?",
        (host_id,),
    ).fetchone()
    linked_count = int(linked_count_row["linked_count"] or 0) if linked_count_row else 0
    if linked_count > 0:
        raise sqlite3.IntegrityError("Host has linked IP assets.")

    cursor = connection.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
    connection.commit()
    return cursor.rowcount > 0



def create_vendor(connection: sqlite3.Connection, name: str) -> Vendor:
    cursor = connection.execute("INSERT INTO vendors (name) VALUES (?)", (name,))
    connection.commit()
    return Vendor(id=cursor.lastrowid, name=name)


def list_vendors(connection: sqlite3.Connection) -> Iterable[Vendor]:
    rows = connection.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()
    return [_row_to_vendor(row) for row in rows]


def get_vendor_by_id(connection: sqlite3.Connection, vendor_id: int) -> Optional[Vendor]:
    row = connection.execute("SELECT id, name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    return _row_to_vendor(row) if row else None


def get_vendor_by_name(connection: sqlite3.Connection, name: str) -> Optional[Vendor]:
    row = connection.execute("SELECT id, name FROM vendors WHERE name = ?", (name,)).fetchone()
    return _row_to_vendor(row) if row else None


def update_vendor(connection: sqlite3.Connection, vendor_id: int, name: str) -> Optional[Vendor]:
    connection.execute("UPDATE vendors SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (name, vendor_id))
    connection.commit()
    return get_vendor_by_id(connection, vendor_id)


def create_tag(connection: sqlite3.Connection, name: str, color: Optional[str] = None) -> Tag:
    normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
    cursor = connection.execute(
        "INSERT INTO tags (name, color) VALUES (?, ?)",
        (name, normalized_color),
    )
    connection.commit()
    row = connection.execute("SELECT id, name, color FROM tags WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created tag.")
    return _row_to_tag(row)


def list_tags(connection: sqlite3.Connection) -> Iterable[Tag]:
    rows = connection.execute("SELECT id, name, color FROM tags ORDER BY name").fetchall()
    return [_row_to_tag(row) for row in rows]


def get_tag_by_id(connection: sqlite3.Connection, tag_id: int) -> Optional[Tag]:
    row = connection.execute("SELECT id, name, color FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return _row_to_tag(row) if row else None


def get_tag_by_name(connection: sqlite3.Connection, name: str) -> Optional[Tag]:
    row = connection.execute("SELECT id, name, color FROM tags WHERE name = ?", (name,)).fetchone()
    return _row_to_tag(row) if row else None


def update_tag(connection: sqlite3.Connection, tag_id: int, name: str, color: Optional[str] = None) -> Optional[Tag]:
    normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
    connection.execute(
        "UPDATE tags SET name = ?, color = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, normalized_color, tag_id),
    )
    connection.commit()
    return get_tag_by_id(connection, tag_id)


def delete_tag(connection: sqlite3.Connection, tag_id: int) -> bool:
    with connection:
        connection.execute("DELETE FROM ip_asset_tags WHERE tag_id = ?", (tag_id,))
        cursor = connection.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    return cursor.rowcount > 0


def list_tag_details_for_ip_assets(
    connection: sqlite3.Connection,
    asset_ids: Iterable[int],
) -> dict[int, list[dict[str, str]]]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return {}
    placeholders = ",".join(["?"] * len(asset_ids_list))
    rows = connection.execute(
        f"""
        SELECT ip_asset_tags.ip_asset_id AS asset_id,
               tags.name AS tag_name,
               tags.color AS tag_color
        FROM ip_asset_tags
        JOIN tags ON tags.id = ip_asset_tags.tag_id
        WHERE ip_asset_tags.ip_asset_id IN ({placeholders})
        ORDER BY tags.name
        """,
        asset_ids_list,
    ).fetchall()
    mapping: dict[int, list[dict[str, str]]] = {asset_id: [] for asset_id in asset_ids_list}
    for row in rows:
        mapping.setdefault(row["asset_id"], []).append(
            {"name": row["tag_name"], "color": row["tag_color"]}
        )
    return mapping


def list_tags_for_ip_assets(connection: sqlite3.Connection, asset_ids: Iterable[int]) -> dict[int, list[str]]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return {}
    placeholders = ",".join(["?"] * len(asset_ids_list))
    rows = connection.execute(
        f"""
        SELECT ip_asset_tags.ip_asset_id AS asset_id,
               tags.name AS tag_name
        FROM ip_asset_tags
        JOIN tags ON tags.id = ip_asset_tags.tag_id
        WHERE ip_asset_tags.ip_asset_id IN ({placeholders})
        ORDER BY tags.name
        """,
        asset_ids_list,
    ).fetchall()
    mapping: dict[int, list[str]] = {asset_id: [] for asset_id in asset_ids_list}
    for row in rows:
        mapping.setdefault(row["asset_id"], []).append(row["tag_name"])
    return mapping


def set_ip_asset_tags(connection: sqlite3.Connection, asset_id: int, tag_names: Iterable[str]) -> list[str]:
    normalized_tags = normalize_tag_names(list(tag_names))
    connection.execute("DELETE FROM ip_asset_tags WHERE ip_asset_id = ?", (asset_id,))
    if not normalized_tags:
        return []
    for tag_name in normalized_tags:
        connection.execute(
            "INSERT INTO tags (name) VALUES (?) ON CONFLICT(name) DO NOTHING",
            (tag_name,),
        )
    placeholders = ",".join(["?"] * len(normalized_tags))
    rows = connection.execute(
        f"SELECT id, name FROM tags WHERE name IN ({placeholders})",
        normalized_tags,
    ).fetchall()
    tag_ids = {row["name"]: row["id"] for row in rows}
    for tag_name in normalized_tags:
        tag_id = tag_ids.get(tag_name)
        if tag_id is None:
            continue
        connection.execute(
            "INSERT INTO ip_asset_tags (ip_asset_id, tag_id) VALUES (?, ?)",
            (asset_id, tag_id),
        )
    return normalized_tags

def create_ip_asset(
    connection: sqlite3.Connection,
    ip_address: str,
    asset_type: IPAssetType,
    project_id: Optional[int] = None,
    host_id: Optional[int] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    auto_host_for_bmc: bool = False,
    current_user: Optional[User] = None,
) -> IPAsset:
    resolved_host_id = host_id
    with connection:
        if auto_host_for_bmc and asset_type == IPAssetType.BMC and resolved_host_id is None:
            host_name = f"server_{ip_address}"
            existing_host = connection.execute("SELECT id FROM hosts WHERE name = ?", (host_name,)).fetchone()
            if existing_host is None:
                host_cursor = connection.execute("INSERT INTO hosts (name, notes) VALUES (?, ?)", (host_name, None))
                resolved_host_id = host_cursor.lastrowid
            else:
                resolved_host_id = existing_host["id"]

        cursor = connection.execute(
            "INSERT INTO ip_assets (ip_address, type, project_id, host_id, notes) VALUES (?, ?, ?, ?, ?)",
            (ip_address, asset_type.value, project_id, resolved_host_id, notes),
        )
        create_audit_log(
            connection,
            user=current_user,
            action="CREATE",
            target_type="IP_ASSET",
            target_id=cursor.lastrowid,
            target_label=ip_address,
            changes=(
                "Created IP asset "
                f"(type={asset_type.value}, project_id={project_id}, host_id={resolved_host_id}, notes={notes or ''})"
            ),
        )
        if tags is not None:
            set_ip_asset_tags(connection, cursor.lastrowid, tags)
    row = connection.execute("SELECT * FROM ip_assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created IP asset.")
    return _row_to_ip_asset(row)


def get_ip_asset_by_ip(connection: sqlite3.Connection, ip_address: str) -> Optional[IPAsset]:
    row = connection.execute("SELECT * FROM ip_assets WHERE ip_address = ?", (ip_address,)).fetchone()
    return _row_to_ip_asset(row) if row else None


def get_ip_asset_by_id(connection: sqlite3.Connection, asset_id: int) -> Optional[IPAsset]:
    row = connection.execute("SELECT * FROM ip_assets WHERE id = ?", (asset_id,)).fetchone()
    return _row_to_ip_asset(row) if row else None


def list_ip_assets_by_ids(connection: sqlite3.Connection, asset_ids: Iterable[int]) -> list[IPAsset]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return []
    placeholders = ",".join(["?"] * len(asset_ids_list))
    rows = connection.execute(
        f"SELECT * FROM ip_assets WHERE id IN ({placeholders}) ORDER BY ip_address",
        asset_ids_list,
    ).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def list_active_ip_assets(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    archived_only: bool = False,
) -> Iterable[IPAsset]:
    query = "SELECT * FROM ip_assets WHERE archived = ?"
    params: list[object] = []
    params.append(1 if archived_only else 0)
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if asset_type is not None:
        query += " AND type = ?"
        params.append(asset_type.value)
    if unassigned_only:
        query += " AND project_id IS NULL"
    query += " ORDER BY ip_address"
    rows = connection.execute(query, params).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def count_active_ip_assets(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    archived_only: bool = False,
) -> int:
    query = "SELECT COUNT(*) FROM ip_assets WHERE archived = ?"
    params: list[object] = []
    params.append(1 if archived_only else 0)
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if asset_type is not None:
        query += " AND type = ?"
        params.append(asset_type.value)
    if unassigned_only:
        query += " AND project_id IS NULL"
    if query_text:
        query += " AND (LOWER(ip_address) LIKE ? OR LOWER(COALESCE(notes, '')) LIKE ?)"
        query_value = f"%{query_text.lower()}%"
        params.extend([query_value, query_value])
    return int(connection.execute(query, params).fetchone()[0])


def list_active_ip_assets_paginated(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    archived_only: bool = False,
) -> list[IPAsset]:
    query = "SELECT * FROM ip_assets WHERE archived = ?"
    params: list[object] = []
    params.append(1 if archived_only else 0)
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if asset_type is not None:
        query += " AND type = ?"
        params.append(asset_type.value)
    if unassigned_only:
        query += " AND project_id IS NULL"
    if query_text:
        query += " AND (LOWER(ip_address) LIKE ? OR LOWER(COALESCE(notes, '')) LIKE ?)"
        query_value = f"%{query_text.lower()}%"
        params.extend([query_value, query_value])
    query += " ORDER BY ip_address LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = connection.execute(query, params).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def list_sd_targets(connection: sqlite3.Connection, port: int, only_assigned: bool = False, project_names: Optional[list[str]] = None, asset_types: Optional[list[IPAssetType]] = None, group_by: str = "none") -> list[dict[str, object]]:
    query = "SELECT ip_assets.ip_address AS ip_address, ip_assets.type AS asset_type, projects.name AS project_name FROM ip_assets LEFT JOIN projects ON projects.id = ip_assets.project_id WHERE ip_assets.archived = 0"
    params: list[object] = []
    if only_assigned:
        query += " AND ip_assets.project_id IS NOT NULL"
    if project_names:
        placeholders = ",".join(["?"] * len(project_names))
        query += f" AND projects.name IN ({placeholders})"
        params.extend(project_names)
    if asset_types:
        placeholders = ",".join(["?"] * len(asset_types))
        query += f" AND ip_assets.type IN ({placeholders})"
        params.extend([asset_type.value for asset_type in asset_types])
    query += " ORDER BY ip_assets.ip_address"
    rows = connection.execute(query, params).fetchall()

    grouped: dict[tuple[str, ...], list[sqlite3.Row]] = {}
    for row in rows:
        project = row["project_name"] or "unassigned"
        key = (project,) if group_by == "project" else ("all",)
        grouped.setdefault(key, []).append(row)

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        group_rows = grouped[key]
        projects = {r["project_name"] or "unassigned" for r in group_rows}
        project_label = next(iter(projects)) if len(projects) == 1 else "multiple"
        types = {r["asset_type"] for r in group_rows}
        type_label = next(iter(types)) if len(types) == 1 else "multiple"
        output.append({
            "targets": [f"{r['ip_address']}:{port}" for r in group_rows],
            "labels": {"project": project_label, "type": type_label},
        })
    return output


def list_ip_assets_needing_assignment(connection: sqlite3.Connection, filter_mode: str) -> Iterable[IPAsset]:
    if filter_mode != "project":
        raise ValueError("Invalid assignment filter mode.")
    rows = connection.execute("SELECT * FROM ip_assets WHERE archived = 0 AND project_id IS NULL ORDER BY ip_address").fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def list_ip_assets_for_export(
    connection: sqlite3.Connection,
    include_archived: bool = False,
    asset_type: Optional[IPAssetType] = None,
    project_name: Optional[str] = None,
    host_name: Optional[str] = None,
) -> list[dict[str, object]]:
    query = """
        SELECT ip_assets.id AS asset_id,
               ip_assets.ip_address AS ip_address,
               ip_assets.type AS asset_type,
               projects.name AS project_name,
               hosts.name AS host_name,
               ip_assets.notes AS notes,
               ip_assets.archived AS archived,
               ip_assets.created_at AS created_at,
               ip_assets.updated_at AS updated_at
        FROM ip_assets
        LEFT JOIN projects ON projects.id = ip_assets.project_id
        LEFT JOIN hosts ON hosts.id = ip_assets.host_id
    """
    filters: list[str] = []
    params: list[object] = []
    if not include_archived:
        filters.append("ip_assets.archived = 0")
    if asset_type is not None:
        filters.append("ip_assets.type = ?")
        params.append(asset_type.value)
    if project_name:
        filters.append("projects.name = ?")
        params.append(project_name)
    if host_name:
        filters.append("hosts.name = ?")
        params.append(host_name)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY ip_assets.ip_address"
    rows = connection.execute(query, params).fetchall()
    tag_map = list_tags_for_ip_assets(connection, [row["asset_id"] for row in rows])
    return [
        {
            "ip_address": row["ip_address"],
            "type": row["asset_type"],
            "project_name": row["project_name"],
            "host_name": row["host_name"],
            "notes": row["notes"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "tags": tag_map.get(row["asset_id"], []),
        }
        for row in rows
    ]


def get_ip_asset_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived_total,
               SUM(CASE WHEN archived = 0 AND project_id IS NULL THEN 1 ELSE 0 END) AS unassigned_project_total,
               0 AS unassigned_owner_total,
               0 AS unassigned_both_total
        FROM ip_assets
        """
    ).fetchone()
    if row is None:
        return {
            "total": 0,
            "archived_total": 0,
            "unassigned_project_total": 0,
            "unassigned_owner_total": 0,
            "unassigned_both_total": 0,
        }
    return {
        "total": int(row["total"] or 0),
        "archived_total": int(row["archived_total"] or 0),
        "unassigned_project_total": int(row["unassigned_project_total"] or 0),
        "unassigned_owner_total": int(row["unassigned_owner_total"] or 0),
        "unassigned_both_total": int(row["unassigned_both_total"] or 0),
    }


def archive_ip_asset(connection: sqlite3.Connection, ip_address: str) -> None:
    connection.execute("UPDATE ip_assets SET archived = 1, updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?", (ip_address,))
    connection.commit()


def set_ip_asset_archived(connection: sqlite3.Connection, ip_address: str, archived: bool) -> None:
    connection.execute(
        "UPDATE ip_assets SET archived = ?, updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?",
        (1 if archived else 0, ip_address),
    )
    connection.commit()


def delete_ip_asset(connection: sqlite3.Connection, ip_address: str, current_user: Optional[User] = None) -> bool:
    asset = get_ip_asset_by_ip(connection, ip_address)
    if asset is None:
        return False
    with connection:
        cursor = connection.execute("DELETE FROM ip_assets WHERE ip_address = ?", (ip_address,))
        if cursor.rowcount > 0:
            create_audit_log(
                connection,
                user=current_user,
                action="DELETE",
                target_type="IP_ASSET",
                target_id=asset.id,
                target_label=asset.ip_address,
                changes="Deleted IP asset.",
            )
    return cursor.rowcount > 0


def update_ip_asset(
    connection: sqlite3.Connection,
    ip_address: str,
    asset_type: Optional[IPAssetType] = None,
    project_id: Optional[int] = None,
    host_id: Optional[int] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    current_user: Optional[User] = None,
) -> Optional[IPAsset]:
    existing = get_ip_asset_by_ip(connection, ip_address)
    if existing is None:
        return None
    with connection:
        connection.execute(
            """
            UPDATE ip_assets
            SET type = COALESCE(?, type),
                project_id = COALESCE(?, project_id), host_id = COALESCE(?, host_id), notes = COALESCE(?, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE ip_address = ?
            """,
            (asset_type.value if asset_type else None, project_id, host_id, notes, ip_address),
        )
        updated = get_ip_asset_by_ip(connection, ip_address)
        if updated is not None:
            create_audit_log(
                connection,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=updated.id,
                target_label=updated.ip_address,
                changes=_summarize_ip_asset_changes(connection, existing, updated),
            )
        if updated is not None and tags is not None:
            set_ip_asset_tags(connection, updated.id, tags)
    return updated


def bulk_update_ip_assets(
    connection: sqlite3.Connection,
    asset_ids: Iterable[int],
    asset_type: Optional[IPAssetType] = None,
    project_id: Optional[int] = None,
    set_project_id: bool = False,
    tags_to_add: Optional[list[str]] = None,
    current_user: Optional[User] = None,
) -> list[IPAsset]:
    assets = list_ip_assets_by_ids(connection, asset_ids)
    if not assets:
        return []
    normalized_tags = normalize_tag_names(tags_to_add) if tags_to_add else []
    tag_map = list_tags_for_ip_assets(connection, [asset.id for asset in assets])
    updated_assets: list[IPAsset] = []
    with connection:
        for asset in assets:
            next_type = asset_type or asset.asset_type
            next_project_id = project_id if set_project_id else asset.project_id
            connection.execute(
                """
                UPDATE ip_assets
                SET type = ?, project_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_type.value, next_project_id, asset.id),
            )
            updated = get_ip_asset_by_id(connection, asset.id)
            if updated is None:
                continue
            create_audit_log(
                connection,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=updated.id,
                target_label=updated.ip_address,
                changes=_summarize_ip_asset_changes(connection, asset, updated),
            )
            if normalized_tags:
                existing_tags = tag_map.get(asset.id, [])
                combined_tags = normalize_tag_names(existing_tags + normalized_tags)
                set_ip_asset_tags(connection, updated.id, combined_tags)
            updated_assets.append(updated)
    return updated_assets
