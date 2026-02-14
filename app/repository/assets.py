from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from app.models import IPAsset, IPAssetType, User
from app.utils import normalize_tag_names
from ._asset_audit import (
    _host_label as _host_label,
    _project_label as _project_label,
    _summarize_ip_asset_changes as _summarize_ip_asset_changes,
)
from ._asset_filters import count_active_assets, list_active_assets
from ._asset_tags import (
    list_tag_details_for_ip_assets as list_tag_details_for_ip_assets,
    list_tags_for_ip_assets as list_tags_for_ip_assets,
    set_ip_asset_tags as set_ip_asset_tags,
)
from .audit import create_audit_log
from .mappers import _row_to_ip_asset


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
        if (
            auto_host_for_bmc
            and asset_type == IPAssetType.BMC
            and resolved_host_id is None
        ):
            host_name = f"server_{ip_address}"
            existing_host = connection.execute(
                "SELECT id FROM hosts WHERE name = ?", (host_name,)
            ).fetchone()
            if existing_host is None:
                host_cursor = connection.execute(
                    "INSERT INTO hosts (name, notes) VALUES (?, ?)", (host_name, None)
                )
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
    return _row_to_ip_asset(row) if row else None


def get_ip_asset_by_id(
    connection: sqlite3.Connection, asset_id: int
) -> Optional[IPAsset]:
    row = connection.execute(
        "SELECT * FROM ip_assets WHERE id = ?", (asset_id,)
    ).fetchone()
    return _row_to_ip_asset(row) if row else None


def list_ip_assets_by_ids(
    connection: sqlite3.Connection, asset_ids: Iterable[int]
) -> list[IPAsset]:
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
    project_unassigned_only: bool = False,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    archived_only: bool = False,
) -> Iterable[IPAsset]:
    return list_active_assets(
        connection,
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=None,
        tag_names=None,
        archived_only=archived_only,
    )


def count_active_ip_assets(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    project_unassigned_only: bool = False,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    tag_names: Optional[list[str]] = None,
    archived_only: bool = False,
) -> int:
    return count_active_assets(
        connection,
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )


def list_active_ip_assets_paginated(
    connection: sqlite3.Connection,
    project_id: Optional[int] = None,
    project_unassigned_only: bool = False,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    tag_names: Optional[list[str]] = None,
    limit: int = 20,
    offset: int = 0,
    archived_only: bool = False,
) -> list[IPAsset]:
    return list_active_assets(
        connection,
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
        limit=limit,
        offset=offset,
    )


def list_sd_targets(
    connection: sqlite3.Connection,
    port: int,
    only_assigned: bool = False,
    project_names: Optional[list[str]] = None,
    asset_types: Optional[list[IPAssetType]] = None,
    group_by: str = "none",
) -> list[dict[str, object]]:
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
        output.append(
            {
                "targets": [f"{r['ip_address']}:{port}" for r in group_rows],
                "labels": {"project": project_label, "type": type_label},
            }
        )
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
    connection.execute(
        "UPDATE ip_assets SET archived = 1, updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?",
        (ip_address,),
    )
    connection.commit()


def set_ip_asset_archived(
    connection: sqlite3.Connection, ip_address: str, archived: bool
) -> None:
    connection.execute(
        "UPDATE ip_assets SET archived = ?, updated_at = CURRENT_TIMESTAMP WHERE ip_address = ?",
        (1 if archived else 0, ip_address),
    )
    connection.commit()


def delete_ip_asset(
    connection: sqlite3.Connection, ip_address: str, current_user: Optional[User] = None
) -> bool:
    asset = get_ip_asset_by_ip(connection, ip_address)
    if asset is None:
        return False
    with connection:
        cursor = connection.execute(
            "DELETE FROM ip_assets WHERE ip_address = ?", (ip_address,)
        )
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
    project_id_provided: bool = False,
    host_id: Optional[int] = None,
    host_id_provided: bool = False,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    current_user: Optional[User] = None,
    notes_provided: bool = False,
) -> Optional[IPAsset]:
    existing = get_ip_asset_by_ip(connection, ip_address)
    if existing is None:
        return None
    notes_should_update = notes_provided or notes is not None
    normalized_notes = (
        notes
        if notes is not None and notes.strip()
        else None
        if notes_should_update
        else None
    )
    normalized_tags = normalize_tag_names(tags) if tags is not None else None
    existing_tags: list[str] = []
    tags_changed = False
    if normalized_tags is not None:
        existing_tags = list_tags_for_ip_assets(connection, [existing.id]).get(
            existing.id, []
        )
        tags_changed = sorted(existing_tags) != sorted(normalized_tags)
    project_should_update = project_id_provided or project_id is not None
    host_should_update = host_id_provided or host_id is not None
    updated_type = asset_type or existing.asset_type
    updated_project_id = project_id if project_should_update else existing.project_id
    updated_host_id = host_id if host_should_update else existing.host_id
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
                    project_id = CASE WHEN ? THEN ? ELSE project_id END,
                    host_id = CASE WHEN ? THEN ? ELSE host_id END,
                    notes = CASE WHEN ? THEN ? ELSE notes END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ip_address = ?
                """,
                (
                    asset_type.value if asset_type else None,
                    project_should_update,
                    project_id,
                    host_should_update,
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
    tags_to_remove: Optional[list[str]] = None,
    current_user: Optional[User] = None,
) -> list[IPAsset]:
    assets = list_ip_assets_by_ids(connection, asset_ids)
    if not assets:
        return []
    normalized_tags_to_add = normalize_tag_names(tags_to_add) if tags_to_add else []
    normalized_tags_to_remove = (
        normalize_tag_names(tags_to_remove) if tags_to_remove else []
    )
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
            existing_tags = tag_map.get(asset.id, [])
            next_tags = normalize_tag_names(
                [
                    *existing_tags,
                    *normalized_tags_to_add,
                ]
            )
            if normalized_tags_to_remove:
                removal_set = set(normalized_tags_to_remove)
                next_tags = [tag for tag in next_tags if tag not in removal_set]
            create_audit_log(
                connection,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=updated.id,
                target_label=updated.ip_address,
                changes=_summarize_ip_asset_changes(
                    connection,
                    asset,
                    updated,
                    tags_before=existing_tags,
                    tags_after=next_tags,
                ),
            )
            if (
                normalized_tags_to_add
                or normalized_tags_to_remove
                or sorted(existing_tags) != sorted(next_tags)
            ):
                set_ip_asset_tags(connection, updated.id, next_tags)
            updated_assets.append(updated)
    return updated_assets
