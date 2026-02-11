from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import IPAsset, IPAssetType, User
from app.utils import normalize_tag_names
from .audit import create_audit_log
from .mappers import _ip_address_sort_key, _row_to_ip_asset


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



def _summarize_ip_asset_changes(
    connection: sqlite3.Connection,
    existing: IPAsset,
    updated: IPAsset,
    *,
    tags_before: Optional[list[str]] = None,
    tags_after: Optional[list[str]] = None,
) -> str:
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
    if tags_before is not None and tags_after is not None and sorted(tags_before) != sorted(tags_after):
        before_label = ", ".join(tags_before) if tags_before else "none"
        after_label = ", ".join(tags_after) if tags_after else "none"
        changes.append(f"tags: {before_label} -> {after_label}")
    return "; ".join(changes) if changes else "No changes recorded."



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
    assets = [_row_to_ip_asset(row) for row in rows]
    return sorted(assets, key=lambda asset: _ip_address_sort_key(asset.ip_address))



def count_active_ip_assets(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    tag_names: Optional[list[str]] = None,
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
    normalized_tag_names = [tag.strip() for tag in (tag_names or []) if tag and tag.strip()]
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
    return int(connection.execute(query, params).fetchone()[0])



def list_active_ip_assets_paginated(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    tag_names: Optional[list[str]] = None,
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
    normalized_tag_names = [tag.strip() for tag in (tag_names or []) if tag and tag.strip()]
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
    query += " ORDER BY ip_address"
    rows = connection.execute(query, params).fetchall()
    sorted_assets = sorted((
        _row_to_ip_asset(row)
        for row in rows
    ), key=lambda asset: _ip_address_sort_key(asset.ip_address))
    return sorted_assets[offset : offset + limit]



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
    notes_provided: bool = False,
) -> Optional[IPAsset]:
    existing = get_ip_asset_by_ip(connection, ip_address)
    if existing is None:
        return None
    notes_should_update = notes_provided or notes is not None
    normalized_notes = notes if notes is not None and notes.strip() else None if notes_should_update else None
    normalized_tags = normalize_tag_names(tags) if tags is not None else None
    existing_tags: list[str] = []
    tags_changed = False
    if normalized_tags is not None:
        existing_tags = list_tags_for_ip_assets(connection, [existing.id]).get(existing.id, [])
        tags_changed = sorted(existing_tags) != sorted(normalized_tags)
    updated_type = asset_type or existing.asset_type
    updated_project_id = project_id if project_id is not None else existing.project_id
    updated_host_id = host_id if host_id is not None else existing.host_id
    updated_notes = normalized_notes if notes_should_update else existing.notes
    fields_changed = (
        existing.asset_type != updated_type
        or existing.project_id != updated_project_id
        or existing.host_id != updated_host_id
        or (existing.notes or "") != (updated_notes or "")
    )
    if not fields_changed and not tags_changed:
        return existing
    with connection:
        if fields_changed:
            connection.execute(
                """
                UPDATE ip_assets
                SET type = COALESCE(?, type),
                    project_id = COALESCE(?, project_id),
                    host_id = COALESCE(?, host_id),
                    notes = CASE WHEN ? THEN ? ELSE notes END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ip_address = ?
                """,
                (
                    asset_type.value if asset_type else None,
                    project_id,
                    host_id,
                    notes_should_update,
                    normalized_notes,
                    ip_address,
                ),
            )
        else:
            connection.execute(
                "UPDATE ip_assets SET updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?",
                (ip_address,),
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
                changes=_summarize_ip_asset_changes(
                    connection,
                    existing,
                    updated,
                    tags_before=existing_tags if normalized_tags is not None else None,
                    tags_after=normalized_tags,
                ),
            )
        if updated is not None and tags_changed and normalized_tags is not None:
            set_ip_asset_tags(connection, updated.id, normalized_tags)
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
