from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import IPAsset


def _project_label(connection: sqlite3.Connection, project_id: Optional[int]) -> str:
    if project_id is None:
        return "Unassigned"
    project = connection.execute(
        "SELECT name FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if project is None:
        return f"Unknown ({project_id})"
    return project["name"]


def _host_label(connection: sqlite3.Connection, host_id: Optional[int]) -> str:
    if host_id is None:
        return "Unassigned"
    host = connection.execute(
        "SELECT name FROM hosts WHERE id = ?", (host_id,)
    ).fetchone()
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
        changes.append(
            f"type: {existing.asset_type.value} -> {updated.asset_type.value}"
        )
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
    if (
        tags_before is not None
        and tags_after is not None
        and sorted(tags_before) != sorted(tags_after)
    ):
        before_label = ", ".join(tags_before) if tags_before else "none"
        after_label = ", ".join(tags_after) if tags_after else "none"
        changes.append(f"tags: {before_label} -> {after_label}")
    return "; ".join(changes) if changes else "No changes recorded."
