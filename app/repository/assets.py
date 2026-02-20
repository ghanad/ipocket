from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from sqlalchemy import case, func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAsset, IPAssetType, User
from app.utils import normalize_tag_names

from ._asset_audit import (
    _summarize_ip_asset_changes as _summarize_ip_asset_changes,
)
from ._asset_filters import count_active_assets, list_active_assets
from ._asset_tags import (
    list_tag_details_for_ip_assets as list_tag_details_for_ip_assets,
    list_tags_for_ip_assets as list_tags_for_ip_assets,
    set_ip_asset_tags as set_ip_asset_tags,
)
from ._db import (
    reraise_as_sqlite_integrity_error,
    session_scope,
    write_session_scope,
)
from .audit import create_audit_log
from .mappers import _row_to_ip_asset


def _asset_columns():
    return (
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


def create_ip_asset(
    connection_or_session: sqlite3.Connection | Session,
    ip_address: str,
    asset_type: IPAssetType,
    project_id: Optional[int] = None,
    host_id: Optional[int] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
    auto_host_for_bmc: bool = False,
    current_user: Optional[User] = None,
) -> IPAsset:
    with write_session_scope(connection_or_session) as session:
        resolved_host_id = host_id
        if (
            auto_host_for_bmc
            and asset_type == IPAssetType.BMC
            and resolved_host_id is None
        ):
            host_name = f"server_{ip_address}"
            existing_host_id = session.scalar(
                select(db_schema.Host.id).where(db_schema.Host.name == host_name)
            )
            if existing_host_id is None:
                host_model = db_schema.Host(name=host_name, notes=None)
                session.add(host_model)
                session.flush()
                resolved_host_id = int(host_model.id)
            else:
                resolved_host_id = int(existing_host_id)

        existing = (
            session.execute(
                select(*_asset_columns()).where(
                    db_schema.IPAsset.ip_address == ip_address
                )
            )
            .mappings()
            .first()
        )
        if existing and int(existing["archived"]) == 0:
            raise sqlite3.IntegrityError("IP address already exists.")
        if existing and int(existing["archived"]) == 1:
            session.execute(
                update(db_schema.IPAsset)
                .where(db_schema.IPAsset.id == int(existing["id"]))
                .values(
                    type=asset_type.value,
                    project_id=project_id,
                    host_id=resolved_host_id,
                    notes=notes,
                    archived=0,
                    updated_at=func.current_timestamp(),
                )
            )
            restored = get_ip_asset_by_ip(session, ip_address)
            if restored is None:
                raise RuntimeError("Failed to fetch restored IP asset.")
            create_audit_log(
                session,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=restored.id,
                target_label=restored.ip_address,
                changes=(
                    "Restored archived IP asset "
                    f"(type={asset_type.value}, project_id={project_id}, host_id={resolved_host_id}, notes={notes or ''})"
                ),
            )
            if tags is not None:
                set_ip_asset_tags(session, restored.id, tags)
            if not isinstance(connection_or_session, Session):
                session.commit()
            return restored

        model = db_schema.IPAsset(
            ip_address=ip_address,
            type=asset_type.value,
            project_id=project_id,
            host_id=resolved_host_id,
            notes=notes,
        )
        try:
            session.add(model)
            session.flush()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)

        create_audit_log(
            session,
            user=current_user,
            action="CREATE",
            target_type="IP_ASSET",
            target_id=int(model.id),
            target_label=ip_address,
            changes=(
                "Created IP asset "
                f"(type={asset_type.value}, project_id={project_id}, host_id={resolved_host_id}, notes={notes or ''})"
            ),
        )
        if tags is not None:
            set_ip_asset_tags(session, int(model.id), tags)
        session.commit()
        session.refresh(model)
    return _row_to_ip_asset(
        {
            "id": model.id,
            "ip_address": model.ip_address,
            "type": model.type,
            "project_id": model.project_id,
            "host_id": model.host_id,
            "notes": model.notes,
            "archived": model.archived,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
    )


def get_ip_asset_by_ip(
    connection_or_session: sqlite3.Connection | Session, ip_address: str
) -> Optional[IPAsset]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(*_asset_columns()).where(
                    db_schema.IPAsset.ip_address == ip_address
                )
            )
            .mappings()
            .first()
        )
    return _row_to_ip_asset(row) if row else None


def get_ip_asset_by_id(
    connection_or_session: sqlite3.Connection | Session, asset_id: int
) -> Optional[IPAsset]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(*_asset_columns()).where(db_schema.IPAsset.id == asset_id)
            )
            .mappings()
            .first()
        )
    return _row_to_ip_asset(row) if row else None


def list_ip_assets_by_ids(
    connection_or_session: sqlite3.Connection | Session, asset_ids: Iterable[int]
) -> list[IPAsset]:
    asset_ids_list = list(asset_ids)
    if not asset_ids_list:
        return []
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(*_asset_columns())
                .where(db_schema.IPAsset.id.in_(asset_ids_list))
                .order_by(db_schema.IPAsset.ip_address)
            )
            .mappings()
            .all()
        )
    return [_row_to_ip_asset(row) for row in rows]


def list_active_ip_assets(
    connection_or_session: sqlite3.Connection | Session,
    project_id: Optional[int] = None,
    project_unassigned_only: bool = False,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    archived_only: bool = False,
) -> Iterable[IPAsset]:
    return list_active_assets(
        connection_or_session,
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=None,
        tag_names=None,
        archived_only=archived_only,
    )


def count_active_ip_assets(
    connection_or_session: sqlite3.Connection | Session,
    project_id: Optional[int] = None,
    project_unassigned_only: bool = False,
    asset_type: Optional[IPAssetType] = None,
    unassigned_only: bool = False,
    query_text: Optional[str] = None,
    tag_names: Optional[list[str]] = None,
    archived_only: bool = False,
) -> int:
    return count_active_assets(
        connection_or_session,
        project_id=project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_names,
        archived_only=archived_only,
    )


def list_active_ip_assets_paginated(
    connection_or_session: sqlite3.Connection | Session,
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
        connection_or_session,
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
    connection_or_session: sqlite3.Connection | Session,
    port: int,
    only_assigned: bool = False,
    project_names: Optional[list[str]] = None,
    asset_types: Optional[list[IPAssetType]] = None,
    group_by: str = "none",
) -> list[dict[str, object]]:
    statement = (
        select(
            db_schema.IPAsset.ip_address.label("ip_address"),
            db_schema.IPAsset.type.label("asset_type"),
            db_schema.Project.name.label("project_name"),
        )
        .select_from(db_schema.IPAsset)
        .join(
            db_schema.Project,
            db_schema.Project.id == db_schema.IPAsset.project_id,
            isouter=True,
        )
        .where(db_schema.IPAsset.archived == 0)
    )
    if only_assigned:
        statement = statement.where(db_schema.IPAsset.project_id.is_not(None))
    if project_names:
        statement = statement.where(db_schema.Project.name.in_(project_names))
    if asset_types:
        statement = statement.where(
            db_schema.IPAsset.type.in_([asset_type.value for asset_type in asset_types])
        )
    statement = statement.order_by(db_schema.IPAsset.ip_address)
    with session_scope(connection_or_session) as session:
        rows = session.execute(statement).mappings().all()

    grouped: dict[tuple[str, ...], list[dict[str, object]]] = {}
    for row in rows:
        project = row["project_name"] or "unassigned"
        key = (str(project),) if group_by == "project" else ("all",)
        grouped.setdefault(key, []).append(dict(row))

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        group_rows = grouped[key]
        projects = {str(r["project_name"] or "unassigned") for r in group_rows}
        project_label = next(iter(projects)) if len(projects) == 1 else "multiple"
        types = {str(r["asset_type"]) for r in group_rows}
        type_label = next(iter(types)) if len(types) == 1 else "multiple"
        output.append(
            {
                "targets": [f"{r['ip_address']}:{port}" for r in group_rows],
                "labels": {"project": project_label, "type": type_label},
            }
        )
    return output


def list_ip_assets_for_export(
    connection_or_session: sqlite3.Connection | Session,
    include_archived: bool = False,
    asset_type: Optional[IPAssetType] = None,
    project_name: Optional[str] = None,
    host_name: Optional[str] = None,
) -> list[dict[str, object]]:
    statement = (
        select(
            db_schema.IPAsset.id.label("asset_id"),
            db_schema.IPAsset.ip_address.label("ip_address"),
            db_schema.IPAsset.type.label("asset_type"),
            db_schema.Project.name.label("project_name"),
            db_schema.Host.name.label("host_name"),
            db_schema.IPAsset.notes.label("notes"),
            db_schema.IPAsset.archived.label("archived"),
            db_schema.IPAsset.created_at.label("created_at"),
            db_schema.IPAsset.updated_at.label("updated_at"),
        )
        .select_from(db_schema.IPAsset)
        .join(
            db_schema.Project,
            db_schema.Project.id == db_schema.IPAsset.project_id,
            isouter=True,
        )
        .join(
            db_schema.Host, db_schema.Host.id == db_schema.IPAsset.host_id, isouter=True
        )
    )
    if not include_archived:
        statement = statement.where(db_schema.IPAsset.archived == 0)
    if asset_type is not None:
        statement = statement.where(db_schema.IPAsset.type == asset_type.value)
    if project_name:
        statement = statement.where(db_schema.Project.name == project_name)
    if host_name:
        statement = statement.where(db_schema.Host.name == host_name)
    statement = statement.order_by(db_schema.IPAsset.ip_address)
    with session_scope(connection_or_session) as session:
        rows = session.execute(statement).mappings().all()
    tag_map = list_tags_for_ip_assets(
        connection_or_session, [int(row["asset_id"]) for row in rows]
    )
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
            "tags": tag_map.get(int(row["asset_id"]), []),
        }
        for row in rows
    ]


def get_ip_asset_metrics(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, int]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    func.count().label("total"),
                    func.sum(case((db_schema.IPAsset.archived == 1, 1), else_=0)).label(
                        "archived_total"
                    ),
                    func.sum(
                        case(
                            (
                                (db_schema.IPAsset.archived == 0)
                                & db_schema.IPAsset.project_id.is_(None),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("unassigned_project_total"),
                ).select_from(db_schema.IPAsset)
            )
            .mappings()
            .first()
        )
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
        "unassigned_owner_total": 0,
        "unassigned_both_total": 0,
    }


def archive_ip_asset(
    connection_or_session: sqlite3.Connection | Session, ip_address: str
) -> None:
    with write_session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.IPAsset)
            .where(db_schema.IPAsset.ip_address == ip_address)
            .values(archived=1, updated_at=func.current_timestamp())
        )
        session.commit()


def set_ip_asset_archived(
    connection_or_session: sqlite3.Connection | Session, ip_address: str, archived: bool
) -> None:
    with write_session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.IPAsset)
            .where(db_schema.IPAsset.ip_address == ip_address)
            .values(archived=1 if archived else 0, updated_at=func.current_timestamp())
        )
        session.commit()


def delete_ip_asset(
    connection_or_session: sqlite3.Connection | Session,
    ip_address: str,
    current_user: Optional[User] = None,
) -> bool:
    asset = get_ip_asset_by_ip(connection_or_session, ip_address)
    if asset is None:
        return False
    with write_session_scope(connection_or_session) as session:
        result = session.execute(
            delete(db_schema.IPAsset).where(db_schema.IPAsset.ip_address == ip_address)
        )
        if result.rowcount > 0:
            create_audit_log(
                session,
                user=current_user,
                action="DELETE",
                target_type="IP_ASSET",
                target_id=asset.id,
                target_label=asset.ip_address,
                changes="Deleted IP asset.",
            )
        session.commit()
    return bool(result.rowcount)


def update_ip_asset(
    connection_or_session: sqlite3.Connection | Session,
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
    existing = get_ip_asset_by_ip(connection_or_session, ip_address)
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
        existing_tags = list_tags_for_ip_assets(
            connection_or_session, [existing.id]
        ).get(existing.id, [])
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

    with write_session_scope(connection_or_session) as session:
        if fields_changed:
            values: dict[str, object] = {
                "type": updated_type.value,
                "updated_at": func.current_timestamp(),
            }
            if project_should_update:
                values["project_id"] = project_id
            if host_should_update:
                values["host_id"] = host_id
            if notes_should_update:
                values["notes"] = normalized_notes
            session.execute(
                update(db_schema.IPAsset)
                .where(db_schema.IPAsset.ip_address == ip_address)
                .values(**values)
            )
        else:
            session.execute(
                update(db_schema.IPAsset)
                .where(db_schema.IPAsset.ip_address == ip_address)
                .values(updated_at=func.current_timestamp())
            )

        updated = get_ip_asset_by_ip(session, ip_address)
        if updated is not None:
            create_audit_log(
                session,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=updated.id,
                target_label=updated.ip_address,
                changes=_summarize_ip_asset_changes(
                    session,
                    existing,
                    updated,
                    tags_before=existing_tags if normalized_tags is not None else None,
                    tags_after=normalized_tags,
                ),
            )
        if updated is not None and tags_changed and normalized_tags is not None:
            set_ip_asset_tags(session, updated.id, normalized_tags)
        session.commit()
    return updated


def bulk_update_ip_assets(
    connection_or_session: sqlite3.Connection | Session,
    asset_ids: Iterable[int],
    asset_type: Optional[IPAssetType] = None,
    project_id: Optional[int] = None,
    set_project_id: bool = False,
    tags_to_add: Optional[list[str]] = None,
    tags_to_remove: Optional[list[str]] = None,
    current_user: Optional[User] = None,
) -> list[IPAsset]:
    assets = list_ip_assets_by_ids(connection_or_session, asset_ids)
    if not assets:
        return []
    normalized_tags_to_add = normalize_tag_names(tags_to_add) if tags_to_add else []
    normalized_tags_to_remove = (
        normalize_tag_names(tags_to_remove) if tags_to_remove else []
    )
    tag_map = list_tags_for_ip_assets(
        connection_or_session, [asset.id for asset in assets]
    )
    updated_assets: list[IPAsset] = []
    with write_session_scope(connection_or_session) as session:
        for asset in assets:
            next_type = asset_type or asset.asset_type
            next_project_id = project_id if set_project_id else asset.project_id
            session.execute(
                update(db_schema.IPAsset)
                .where(db_schema.IPAsset.id == asset.id)
                .values(
                    type=next_type.value,
                    project_id=next_project_id,
                    updated_at=func.current_timestamp(),
                )
            )
            updated = get_ip_asset_by_id(session, asset.id)
            if updated is None:
                continue
            existing_tags = tag_map.get(asset.id, [])
            next_tags = normalize_tag_names([*existing_tags, *normalized_tags_to_add])
            if normalized_tags_to_remove:
                removal_set = set(normalized_tags_to_remove)
                next_tags = [tag for tag in next_tags if tag not in removal_set]
            create_audit_log(
                session,
                user=current_user,
                action="UPDATE",
                target_type="IP_ASSET",
                target_id=updated.id,
                target_label=updated.ip_address,
                changes=_summarize_ip_asset_changes(
                    session,
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
                set_ip_asset_tags(session, updated.id, next_tags)
            updated_assets.append(updated)
        session.commit()
    return updated_assets
