from __future__ import annotations

import sqlite3
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAsset, IPAssetType

from ._db import session_scope
from .mappers import _ip_address_sort_key, _row_to_ip_asset


def _apply_asset_filters(
    statement,
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
):
    statement = statement.where(
        db_schema.IPAsset.archived == (1 if archived_only else 0)
    )
    if project_unassigned_only:
        statement = statement.where(db_schema.IPAsset.project_id.is_(None))
    elif project_id is not None:
        statement = statement.where(db_schema.IPAsset.project_id == project_id)
    if asset_type is not None:
        statement = statement.where(db_schema.IPAsset.type == asset_type.value)
    if unassigned_only:
        statement = statement.where(db_schema.IPAsset.project_id.is_(None))
    if query_text:
        like_value = f"%{query_text.lower()}%"
        statement = statement.where(
            func.lower(db_schema.IPAsset.ip_address).like(like_value)
            | func.lower(func.coalesce(db_schema.IPAsset.notes, "")).like(like_value)
        )
    normalized_tag_names = [
        tag.strip().lower() for tag in (tag_names or []) if tag and tag.strip()
    ]
    if normalized_tag_names:
        tag_exists = (
            select(db_schema.IPAssetTag.ip_asset_id)
            .join(db_schema.Tag, db_schema.Tag.id == db_schema.IPAssetTag.tag_id)
            .where(
                db_schema.IPAssetTag.ip_asset_id == db_schema.IPAsset.id,
                func.lower(db_schema.Tag.name).in_(normalized_tag_names),
            )
            .exists()
        )
        statement = statement.where(tag_exists)
    return statement


def _asset_select():
    return select(
        db_schema.IPAsset.id,
        db_schema.IPAsset.ip_address,
        db_schema.IPAsset.type,
        db_schema.IPAsset.project_id,
        db_schema.IPAsset.host_id,
        db_schema.IPAsset.notes,
        db_schema.IPAsset.archived,
        db_schema.IPAsset.created_at,
        db_schema.IPAsset.updated_at,
    )


def count_active_assets(
    connection_or_session: sqlite3.Connection | Session,
    *,
    project_id: Optional[int],
    project_unassigned_only: bool,
    asset_type: Optional[IPAssetType],
    unassigned_only: bool,
    query_text: Optional[str],
    tag_names: Optional[list[str]],
    archived_only: bool,
) -> int:
    statement = _apply_asset_filters(
        select(func.count()).select_from(db_schema.IPAsset),
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    with session_scope(connection_or_session) as session:
        return int(session.scalar(statement) or 0)


def list_active_assets(
    connection_or_session: sqlite3.Connection | Session,
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
    statement = _apply_asset_filters(
        _asset_select(),
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )
    with session_scope(connection_or_session) as session:
        rows = session.execute(statement).mappings().all()
    rows_sorted = sorted(
        rows,
        key=lambda row: (
            _ip_address_sort_key(str(row["ip_address"]))[0],
            _ip_address_sort_key(str(row["ip_address"]))[1],
            _ip_address_sort_key(str(row["ip_address"]))[2],
            str(row["ip_address"]),
        ),
    )
    if limit is not None:
        rows_sorted = rows_sorted[offset : offset + limit]
    return [_row_to_ip_asset(row) for row in rows_sorted]
