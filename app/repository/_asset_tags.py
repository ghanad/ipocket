from __future__ import annotations

import sqlite3
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.utils import normalize_tag_names

from ._db import session_scope, write_session_scope


def list_tag_details_for_ip_assets(
    connection_or_session: sqlite3.Connection | Session,
    asset_ids: Iterable[int],
) -> dict[int, list[dict[str, str]]]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return {}
    with session_scope(connection_or_session) as session:
        rows = session.execute(
            select(
                db_schema.IPAssetTag.ip_asset_id.label("asset_id"),
                db_schema.Tag.name.label("tag_name"),
                db_schema.Tag.color.label("tag_color"),
            )
            .join(db_schema.Tag, db_schema.Tag.id == db_schema.IPAssetTag.tag_id)
            .where(db_schema.IPAssetTag.ip_asset_id.in_(asset_ids_list))
            .order_by(db_schema.Tag.name)
        ).all()
    mapping: dict[int, list[dict[str, str]]] = {
        asset_id: [] for asset_id in asset_ids_list
    }
    for row in rows:
        mapping.setdefault(int(row.asset_id), []).append(
            {"name": str(row.tag_name), "color": str(row.tag_color)}
        )
    return mapping


def list_tags_for_ip_assets(
    connection_or_session: sqlite3.Connection | Session, asset_ids: Iterable[int]
) -> dict[int, list[str]]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return {}
    with session_scope(connection_or_session) as session:
        rows = session.execute(
            select(
                db_schema.IPAssetTag.ip_asset_id.label("asset_id"),
                db_schema.Tag.name.label("tag_name"),
            )
            .join(db_schema.Tag, db_schema.Tag.id == db_schema.IPAssetTag.tag_id)
            .where(db_schema.IPAssetTag.ip_asset_id.in_(asset_ids_list))
            .order_by(db_schema.Tag.name)
        ).all()
    mapping: dict[int, list[str]] = {asset_id: [] for asset_id in asset_ids_list}
    for row in rows:
        mapping.setdefault(int(row.asset_id), []).append(str(row.tag_name))
    return mapping


def set_ip_asset_tags(
    connection_or_session: sqlite3.Connection | Session,
    asset_id: int,
    tag_names: Iterable[str],
) -> list[str]:
    normalized_tags = normalize_tag_names(list(tag_names))
    with write_session_scope(connection_or_session) as session:
        session.execute(
            delete(db_schema.IPAssetTag).where(
                db_schema.IPAssetTag.ip_asset_id == asset_id
            )
        )
        if not normalized_tags:
            if not isinstance(connection_or_session, Session):
                session.commit()
            return []

        for tag_name in normalized_tags:
            session.execute(
                sqlite_insert(db_schema.Tag)
                .values(name=tag_name)
                .on_conflict_do_nothing(index_elements=[db_schema.Tag.name])
            )
        tag_rows = session.execute(
            select(db_schema.Tag.id, db_schema.Tag.name).where(
                db_schema.Tag.name.in_(normalized_tags)
            )
        ).all()
        tag_ids = {str(row.name): int(row.id) for row in tag_rows}
        for tag_name in normalized_tags:
            tag_id = tag_ids.get(tag_name)
            if tag_id is None:
                continue
            session.execute(
                sqlite_insert(db_schema.IPAssetTag).values(
                    ip_asset_id=asset_id,
                    tag_id=tag_id,
                )
            )
        if not isinstance(connection_or_session, Session):
            session.commit()
    return normalized_tags
