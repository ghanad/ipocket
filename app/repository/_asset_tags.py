from __future__ import annotations

import sqlite3
from typing import Iterable

from app.utils import normalize_tag_names


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
    mapping: dict[int, list[dict[str, str]]] = {
        asset_id: [] for asset_id in asset_ids_list
    }
    for row in rows:
        mapping.setdefault(row["asset_id"], []).append(
            {"name": row["tag_name"], "color": row["tag_color"]}
        )
    return mapping


def list_tags_for_ip_assets(
    connection: sqlite3.Connection, asset_ids: Iterable[int]
) -> dict[int, list[str]]:
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


def set_ip_asset_tags(
    connection: sqlite3.Connection, asset_id: int, tag_names: Iterable[str]
) -> list[str]:
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
