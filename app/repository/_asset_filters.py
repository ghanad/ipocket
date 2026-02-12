from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import IPAsset, IPAssetType

from .mappers import _ip_address_sort_key, _row_to_ip_asset


def _build_asset_where_clause(
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
) -> tuple[str, list[object]]:
    where_clause = "WHERE archived = ?"
    params: list[object] = [1 if archived_only else 0]

    if project_unassigned_only:
        where_clause += " AND project_id IS NULL"
    elif project_id is not None:
        where_clause += " AND project_id = ?"
        params.append(project_id)

    if asset_type is not None:
        where_clause += " AND type = ?"
        params.append(asset_type.value)

    if unassigned_only:
        where_clause += " AND project_id IS NULL"

    if query_text:
        where_clause += (
            " AND (LOWER(ip_address) LIKE ? OR LOWER(COALESCE(notes, '')) LIKE ?)"
        )
        query_value = f"%{query_text.lower()}%"
        params.extend([query_value, query_value])

    normalized_tag_names = [
        tag.strip() for tag in (tag_names or []) if tag and tag.strip()
    ]
    if normalized_tag_names:
        placeholders = ",".join(["?"] * len(normalized_tag_names))
        where_clause += f"""
        AND EXISTS (
            SELECT 1
            FROM ip_asset_tags
            JOIN tags ON tags.id = ip_asset_tags.tag_id
            WHERE ip_asset_tags.ip_asset_id = ip_assets.id
              AND LOWER(tags.name) IN ({placeholders})
        )
        """
        params.extend([name.lower() for name in normalized_tag_names])

    return where_clause, params


def _sql_ip_sort_bucket(value: str | None) -> int:
    if value is None:
        return 1
    return _ip_address_sort_key(value)[0]


def _sql_ip_sort_version(value: str | None) -> int:
    if value is None:
        return 0
    return _ip_address_sort_key(value)[1]


def _sql_ip_sort_value(value: str | None) -> str:
    if value is None:
        return ""
    _, version, sort_value = _ip_address_sort_key(value)
    if version == 4:
        return f"{int(sort_value):08x}"
    if version == 6:
        return f"{int(sort_value):032x}"
    return str(sort_value)


def _register_ip_sort_functions(connection: sqlite3.Connection) -> None:
    connection.create_function("ip_sort_bucket", 1, _sql_ip_sort_bucket)
    connection.create_function("ip_sort_version", 1, _sql_ip_sort_version)
    connection.create_function("ip_sort_value", 1, _sql_ip_sort_value)


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
    where_clause, params = _build_asset_where_clause(
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    count_query = f"SELECT COUNT(*) FROM ip_assets {where_clause}"
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
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[IPAsset]:
    _register_ip_sort_functions(connection)
    where_clause, params = _build_asset_where_clause(
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    query = f"""
        SELECT * FROM ip_assets
        {where_clause}
        ORDER BY
            ip_sort_bucket(ip_address),
            ip_sort_version(ip_address),
            ip_sort_value(ip_address),
            ip_address
    """
    query_params = list(params)
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        query_params.extend([limit, offset])

    rows = connection.execute(query, query_params).fetchall()
    return [_row_to_ip_asset(row) for row in rows]
