from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import Host, IPAsset, IPAssetType, Project, User, UserRole, Vendor
from app.utils import DEFAULT_PROJECT_COLOR


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
        subnet=row["subnet"],
        gateway=row["gateway"],
        asset_type=IPAssetType(row["type"]),
        project_id=row["project_id"],
        host_id=row["host_id"],
        notes=row["notes"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
        SELECT hosts.id AS id, hosts.name AS name, hosts.notes AS notes, vendors.name AS vendor, COUNT(ip_assets.id) AS ip_count
        FROM hosts
        LEFT JOIN vendors ON vendors.id = hosts.vendor_id
        LEFT JOIN ip_assets ON ip_assets.host_id = hosts.id AND ip_assets.archived = 0
        GROUP BY hosts.id, hosts.name, hosts.notes, vendors.name
        ORDER BY hosts.name
        """
    ).fetchall()
    return [{"id": row["id"], "name": row["name"], "notes": row["notes"], "vendor": row["vendor"], "ip_count": int(row["ip_count"] or 0)} for row in rows]


def get_host_linked_assets_grouped(connection: sqlite3.Connection, host_id: int) -> dict[str, list[IPAsset]]:
    rows = connection.execute("SELECT * FROM ip_assets WHERE host_id = ? AND archived = 0 ORDER BY ip_address", (host_id,)).fetchall()
    assets = [_row_to_ip_asset(row) for row in rows]
    return {
        "os": [a for a in assets if a.asset_type == IPAssetType.OS],
        "bmc": [a for a in assets if a.asset_type == IPAssetType.BMC],
        "other": [a for a in assets if a.asset_type not in (IPAssetType.OS, IPAssetType.BMC)],
    }


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

def create_ip_asset(
    connection: sqlite3.Connection,
    ip_address: str,
    asset_type: IPAssetType,
    subnet: Optional[str] = None,
    gateway: Optional[str] = None,
    project_id: Optional[int] = None,
    host_id: Optional[int] = None,
    notes: Optional[str] = None,
    auto_host_for_bmc: bool = False,
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
            "INSERT INTO ip_assets (ip_address, subnet, gateway, type, project_id, host_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ip_address, subnet or "", gateway or "", asset_type.value, project_id, resolved_host_id, notes),
        )
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


def list_active_ip_assets(connection: sqlite3.Connection, project_id: Optional[int] = None, asset_type: Optional[IPAssetType] = None, unassigned_only: bool = False) -> Iterable[IPAsset]:
    query = "SELECT * FROM ip_assets WHERE archived = 0"
    params: list[object] = []
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
        SELECT ip_assets.ip_address AS ip_address,
               ip_assets.subnet AS subnet,
               ip_assets.gateway AS gateway,
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
    return [
        {
            "ip_address": row["ip_address"],
            "subnet": row["subnet"],
            "gateway": row["gateway"],
            "type": row["asset_type"],
            "project_name": row["project_name"],
            "host_name": row["host_name"],
            "notes": row["notes"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_ip_asset_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived_total,
               SUM(CASE WHEN archived = 0 AND project_id IS NULL THEN 1 ELSE 0 END) AS unassigned_project_total
        FROM ip_assets
        """
    ).fetchone()
    if row is None:
        return {"total": 0, "archived_total": 0, "unassigned_project_total": 0}
    return {
        "total": int(row["total"] or 0),
        "archived_total": int(row["archived_total"] or 0),
        "unassigned_project_total": int(row["unassigned_project_total"] or 0),
    }


def archive_ip_asset(connection: sqlite3.Connection, ip_address: str) -> None:
    connection.execute("UPDATE ip_assets SET archived = 1, updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?", (ip_address,))
    connection.commit()


def delete_ip_asset(connection: sqlite3.Connection, ip_address: str) -> bool:
    cursor = connection.execute("DELETE FROM ip_assets WHERE ip_address = ?", (ip_address,))
    connection.commit()
    return cursor.rowcount > 0


def update_ip_asset(connection: sqlite3.Connection, ip_address: str, subnet: Optional[str] = None, gateway: Optional[str] = None, asset_type: Optional[IPAssetType] = None, project_id: Optional[int] = None, host_id: Optional[int] = None, notes: Optional[str] = None) -> Optional[IPAsset]:
    connection.execute(
        """
        UPDATE ip_assets
        SET subnet = COALESCE(?, subnet), gateway = COALESCE(?, gateway), type = COALESCE(?, type),
            project_id = COALESCE(?, project_id), host_id = COALESCE(?, host_id), notes = COALESCE(?, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE ip_address = ?
        """,
        (subnet, gateway, asset_type.value if asset_type else None, project_id, host_id, notes, ip_address),
    )
    connection.commit()
    return get_ip_asset_by_ip(connection, ip_address)
