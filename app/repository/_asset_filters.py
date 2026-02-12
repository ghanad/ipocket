from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import IPAsset, IPAssetType

from .mappers import _ip_address_sort_key, _row_to_ip_asset


def _build_asset_filters(
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
) -> tuple[str, list[object]]:
    query = "SELECT * FROM ip_assets WHERE archived = ?"
    params: list[object] = [1 if archived_only else 0]

    if project_unassigned_only:
        query += " AND project_id IS NULL"
    elif project_id is not None:
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

    normalized_tag_names = [
        tag.strip() for tag in (tag_names or []) if tag and tag.strip()
    ]
    if normalized_tag_names:
        placeholders = ",".join(["?"] * len(normalized_tag_names))
        query += f"""
        AND EXISTS (
            SELECT 1
            FROM ip_asset_tags
            JOIN tags ON tags.id = ip_asset_tags.tag_id
            WHERE ip_asset_tags.ip_asset_id = ip_assets.id
              AND LOWER(tags.name) IN ({placeholders})
        )
        """
        params.extend([name.lower() for name in normalized_tag_names])

    return query, params


def count_active_assets(
    connection: sqlite3.Connection,
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
) -> int:
    query, params = _build_asset_filters(
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
    return int(connection.execute(count_query, params).fetchone()[0])


def list_active_assets(
    connection: sqlite3.Connection,
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
) -> list[IPAsset]:
    query, params = _build_asset_filters(
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    query += " ORDER BY ip_address"
    rows = connection.execute(query, params).fetchall()
    assets = [_row_to_ip_asset(row) for row in rows]
    return sorted(assets, key=lambda asset: _ip_address_sort_key(asset.ip_address))
