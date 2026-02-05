from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import IPAsset, IPAssetType, Owner, Project, User, UserRole


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(id=row["id"], name=row["name"], description=row["description"])


def _row_to_owner(row: sqlite3.Row) -> Owner:
    return Owner(id=row["id"], name=row["name"], contact=row["contact"])


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
        owner_id=row["owner_id"],
        notes=row["notes"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_project(
    connection: sqlite3.Connection, name: str, description: Optional[str] = None
) -> Project:
    cursor = connection.execute(
        "INSERT INTO projects (name, description) VALUES (?, ?)", (name, description)
    )
    connection.commit()
    project_id = cursor.lastrowid
    return Project(id=project_id, name=name, description=description)


def get_project_by_name(
    connection: sqlite3.Connection, name: str
) -> Optional[Project]:
    row = connection.execute(
        "SELECT id, name, description FROM projects WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def create_owner(
    connection: sqlite3.Connection, name: str, contact: Optional[str] = None
) -> Owner:
    cursor = connection.execute(
        "INSERT INTO owners (name, contact) VALUES (?, ?)", (name, contact)
    )
    connection.commit()
    owner_id = cursor.lastrowid
    return Owner(id=owner_id, name=name, contact=contact)


def get_owner_by_name(connection: sqlite3.Connection, name: str) -> Optional[Owner]:
    row = connection.execute(
        "SELECT id, name, contact FROM owners WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_owner(row)


def update_project(
    connection: sqlite3.Connection,
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[Project]:
    connection.execute(
        """
        UPDATE projects
        SET name = COALESCE(?, name),
            description = COALESCE(?, description)
        WHERE id = ?
        """,
        (name, description, project_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT id, name, description FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def update_owner(
    connection: sqlite3.Connection,
    owner_id: int,
    name: Optional[str] = None,
    contact: Optional[str] = None,
) -> Optional[Owner]:
    connection.execute(
        """
        UPDATE owners
        SET name = COALESCE(?, name),
            contact = COALESCE(?, contact)
        WHERE id = ?
        """,
        (name, contact, owner_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT id, name, contact FROM owners WHERE id = ?", (owner_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_owner(row)


def create_user(
    connection: sqlite3.Connection,
    username: str,
    hashed_password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    cursor = connection.execute(
        """
        INSERT INTO users (username, hashed_password, role, is_active)
        VALUES (?, ?, ?, ?)
        """,
        (username, hashed_password, role.value, int(is_active)),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created user.")
    return _row_to_user(row)


def count_users(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    if row is None:
        return 0
    return int(row["total"])


def get_user_by_username(
    connection: sqlite3.Connection, username: str
) -> Optional[User]:
    row = connection.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> Optional[User]:
    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def create_ip_asset(
    connection: sqlite3.Connection,
    ip_address: str,
    subnet: str,
    gateway: str,
    asset_type: IPAssetType,
    project_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> IPAsset:
    cursor = connection.execute(
        """
        INSERT INTO ip_assets (
            ip_address, subnet, gateway, type, project_id, owner_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (ip_address, subnet, gateway, asset_type.value, project_id, owner_id, notes),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM ip_assets WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created IP asset.")
    return _row_to_ip_asset(row)


def get_ip_asset_by_ip(
    connection: sqlite3.Connection, ip_address: str
) -> Optional[IPAsset]:
    row = connection.execute(
        "SELECT * FROM ip_assets WHERE ip_address = ?", (ip_address,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_ip_asset(row)


def get_ip_asset_by_id(
    connection: sqlite3.Connection, asset_id: int
) -> Optional[IPAsset]:
    row = connection.execute(
        "SELECT * FROM ip_assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_ip_asset(row)


def list_projects(connection: sqlite3.Connection) -> Iterable[Project]:
    rows = connection.execute(
        "SELECT id, name, description FROM projects ORDER BY name"
    ).fetchall()
    return [_row_to_project(row) for row in rows]


def list_owners(connection: sqlite3.Connection) -> Iterable[Owner]:
    rows = connection.execute(
        "SELECT id, name, contact FROM owners ORDER BY name"
    ).fetchall()
    return [_row_to_owner(row) for row in rows]


def list_active_ip_assets(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
) -> Iterable[IPAsset]:
    query = "SELECT * FROM ip_assets WHERE archived = 0"
    params: list[object] = []

    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if owner_id is not None:
        query += " AND owner_id = ?"
        params.append(owner_id)
    if asset_type is not None:
        query += " AND type = ?"
        params.append(asset_type.value)
    if unassigned_only:
        query += " AND (project_id IS NULL OR owner_id IS NULL)"

    query += " ORDER BY ip_address"

    rows = connection.execute(query, params).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def list_sd_targets(
    connection: sqlite3.Connection,
    port: int,
    only_assigned: bool = False,
    project_names: Optional[list[str]] = None,
    owner_names: Optional[list[str]] = None,
    asset_types: Optional[list[IPAssetType]] = None,
    group_by: str = "none",
) -> list[dict[str, object]]:
    query = """
        SELECT
            ip_assets.ip_address AS ip_address,
            ip_assets.type AS asset_type,
            projects.name AS project_name,
            owners.name AS owner_name
        FROM ip_assets
        LEFT JOIN projects ON projects.id = ip_assets.project_id
        LEFT JOIN owners ON owners.id = ip_assets.owner_id
        WHERE ip_assets.archived = 0
    """
    params: list[object] = []

    if only_assigned:
        query += " AND ip_assets.project_id IS NOT NULL AND ip_assets.owner_id IS NOT NULL"
    if project_names:
        placeholders = ",".join(["?"] * len(project_names))
        query += f" AND projects.name IN ({placeholders})"
        params.extend(project_names)
    if owner_names:
        placeholders = ",".join(["?"] * len(owner_names))
        query += f" AND owners.name IN ({placeholders})"
        params.extend(owner_names)
    if asset_types:
        placeholders = ",".join(["?"] * len(asset_types))
        query += f" AND ip_assets.type IN ({placeholders})"
        params.extend([asset_type.value for asset_type in asset_types])

    query += " ORDER BY ip_assets.ip_address"

    rows = connection.execute(query, params).fetchall()

    def _build_group_labels(group_rows: list[sqlite3.Row]) -> dict[str, str]:
        projects = {row["project_name"] or "unassigned" for row in group_rows}
        owners = {row["owner_name"] or "unassigned" for row in group_rows}
        types = {row["asset_type"] for row in group_rows}

        def _single_or_multiple(values: set[str]) -> str:
            if len(values) == 1:
                return next(iter(values))
            return "multiple"

        return {
            "project": _single_or_multiple(projects),
            "owner": _single_or_multiple(owners),
            "type": _single_or_multiple(types),
        }

    grouped_rows: dict[tuple[str, ...], list[sqlite3.Row]] = {}

    for row in rows:
        project_label = row["project_name"] or "unassigned"
        owner_label = row["owner_name"] or "unassigned"

        if group_by == "project":
            group_key = (project_label,)
        elif group_by == "owner":
            group_key = (owner_label,)
        elif group_by == "project_owner":
            group_key = (project_label, owner_label)
        else:
            group_key = ("all",)

        grouped_rows.setdefault(group_key, []).append(row)

    groups: list[dict[str, object]] = []
    for group_key in sorted(grouped_rows):
        group_rows = grouped_rows[group_key]
        groups.append(
            {
                "targets": [f"{row['ip_address']}:{port}" for row in group_rows],
                "labels": _build_group_labels(group_rows),
            }
        )

    return groups


def list_ip_assets_needing_assignment(
    connection: sqlite3.Connection, filter_mode: str
) -> Iterable[IPAsset]:
    query = "SELECT * FROM ip_assets WHERE archived = 0"
    if filter_mode == "owner":
        query += " AND owner_id IS NULL"
    elif filter_mode == "project":
        query += " AND project_id IS NULL"
    elif filter_mode == "both":
        query += " AND owner_id IS NULL AND project_id IS NULL"
    else:
        raise ValueError("Invalid assignment filter mode.")
    query += " ORDER BY ip_address"
    rows = connection.execute(query).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


def get_ip_asset_metrics(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN archived = 1 THEN 1 ELSE 0 END) AS archived_total,
            SUM(CASE WHEN archived = 0 AND owner_id IS NULL THEN 1 ELSE 0 END)
                AS unassigned_owner_total,
            SUM(CASE WHEN archived = 0 AND project_id IS NULL THEN 1 ELSE 0 END)
                AS unassigned_project_total,
            SUM(
                CASE
                    WHEN archived = 0 AND owner_id IS NULL AND project_id IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS unassigned_both_total
        FROM ip_assets
        """
    ).fetchone()
    if row is None:
        return {
            "total": 0,
            "archived_total": 0,
            "unassigned_owner_total": 0,
            "unassigned_project_total": 0,
            "unassigned_both_total": 0,
        }
    return {
        "total": int(row["total"] or 0),
        "archived_total": int(row["archived_total"] or 0),
        "unassigned_owner_total": int(row["unassigned_owner_total"] or 0),
        "unassigned_project_total": int(row["unassigned_project_total"] or 0),
        "unassigned_both_total": int(row["unassigned_both_total"] or 0),
    }


def archive_ip_asset(connection: sqlite3.Connection, ip_address: str) -> None:
    connection.execute(
        """
        UPDATE ip_assets
        SET archived = 1, updated_at = CURRENT_TIMESTAMP
        WHERE ip_address = ?
        """,
        (ip_address,),
    )
    connection.commit()


def update_ip_asset(
    connection: sqlite3.Connection,
    ip_address: str,
    subnet: Optional[str] = None,
    gateway: Optional[str] = None,
    asset_type: Optional[IPAssetType] = None,
    project_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Optional[IPAsset]:
    connection.execute(
        """
        UPDATE ip_assets
        SET subnet = COALESCE(?, subnet),
            gateway = COALESCE(?, gateway),
            type = COALESCE(?, type),
            project_id = COALESCE(?, project_id),
            owner_id = COALESCE(?, owner_id),
            notes = COALESCE(?, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE ip_address = ?
        """,
        (
            subnet,
            gateway,
            asset_type.value if asset_type else None,
            project_id,
            owner_id,
            notes,
            ip_address,
        ),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM ip_assets WHERE ip_address = ?", (ip_address,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_ip_asset(row)
