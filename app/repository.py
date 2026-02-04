from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import IPAsset, IPAssetType, Owner, Project


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(id=row["id"], name=row["name"], description=row["description"])


def _row_to_owner(row: sqlite3.Row) -> Owner:
    return Owner(id=row["id"], name=row["name"], contact=row["contact"])


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


def list_active_ip_assets(connection: sqlite3.Connection) -> Iterable[IPAsset]:
    rows = connection.execute(
        "SELECT * FROM ip_assets WHERE archived = 0 ORDER BY ip_address"
    ).fetchall()
    return [_row_to_ip_asset(row) for row in rows]


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
