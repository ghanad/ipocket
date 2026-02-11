from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import Project, Tag, Vendor
from app.utils import DEFAULT_PROJECT_COLOR, DEFAULT_TAG_COLOR, normalize_hex_color
from .mappers import _row_to_project, _row_to_tag, _row_to_vendor


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


def delete_project(connection: sqlite3.Connection, project_id: int) -> bool:
    with connection:
        connection.execute("UPDATE ip_assets SET project_id = NULL WHERE project_id = ?", (project_id,))
        cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cursor.rowcount > 0


def list_project_ip_counts(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        SELECT project_id, COUNT(*) AS total
        FROM ip_assets
        WHERE project_id IS NOT NULL AND archived = 0
        GROUP BY project_id
        """
    ).fetchall()
    return {int(row["project_id"]): int(row["total"]) for row in rows}



def create_vendor(connection: sqlite3.Connection, name: str) -> Vendor:
    cursor = connection.execute("INSERT INTO vendors (name) VALUES (?)", (name,))
    connection.commit()
    return Vendor(id=cursor.lastrowid, name=name)



def list_vendors(connection: sqlite3.Connection) -> Iterable[Vendor]:
    rows = connection.execute("SELECT id, name FROM vendors ORDER BY name").fetchall()
    return [_row_to_vendor(row) for row in rows]


def list_vendor_ip_counts(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        SELECT hosts.vendor_id AS vendor_id, COUNT(*) AS total
        FROM ip_assets
        JOIN hosts ON hosts.id = ip_assets.host_id
        WHERE hosts.vendor_id IS NOT NULL AND ip_assets.archived = 0
        GROUP BY hosts.vendor_id
        """
    ).fetchall()
    return {int(row["vendor_id"]): int(row["total"]) for row in rows}



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





def delete_vendor(connection: sqlite3.Connection, vendor_id: int) -> bool:
    with connection:
        connection.execute("UPDATE hosts SET vendor_id = NULL WHERE vendor_id = ?", (vendor_id,))
        cursor = connection.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    return cursor.rowcount > 0

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


def list_tag_ip_counts(connection: sqlite3.Connection) -> dict[int, int]:
    rows = connection.execute(
        """
        SELECT ip_asset_tags.tag_id AS tag_id, COUNT(*) AS total
        FROM ip_asset_tags
        JOIN ip_assets ON ip_assets.id = ip_asset_tags.ip_asset_id
        WHERE ip_assets.archived = 0
        GROUP BY ip_asset_tags.tag_id
        """
    ).fetchall()
    return {int(row["tag_id"]): int(row["total"]) for row in rows}



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
