from __future__ import annotations

import sqlite3
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAsset

from ._db import session_scope


def _project_label(
    connection_or_session: sqlite3.Connection | Session, project_id: Optional[int]
) -> str:
    if project_id is None:
        return "Unassigned"
    with session_scope(connection_or_session) as session:
        project_name = session.scalar(
            select(db_schema.Project.name).where(db_schema.Project.id == project_id)
        )
    if project_name is None:
        return f"Unknown ({project_id})"
    return str(project_name)


def _host_label(
    connection_or_session: sqlite3.Connection | Session, host_id: Optional[int]
) -> str:
    if host_id is None:
        return "Unassigned"
    with session_scope(connection_or_session) as session:
        host_name = session.scalar(
            select(db_schema.Host.name).where(db_schema.Host.id == host_id)
        )
    if host_name is None:
        return f"Unknown ({host_id})"
    return str(host_name)


def _summarize_ip_asset_changes(
    connection_or_session: sqlite3.Connection | Session,
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
            f"project: {_project_label(connection_or_session, existing.project_id)} -> {_project_label(connection_or_session, updated.project_id)}"
        )
    if existing.host_id != updated.host_id:
        changes.append(
            f"host: {_host_label(connection_or_session, existing.host_id)} -> {_host_label(connection_or_session, updated.host_id)}"
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
