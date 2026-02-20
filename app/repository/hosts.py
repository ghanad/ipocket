from __future__ import annotations

import sqlite3
from typing import Iterable, Optional

from sqlalchemy import distinct, func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import Host, IPAsset, IPAssetType

from ._db import (
    reraise_as_sqlite_integrity_error,
    session_scope,
    write_session_scope,
)
from .mappers import _row_to_host, _row_to_ip_asset


def _resolve_vendor_id(
    connection_or_session: sqlite3.Connection | Session, vendor_name: Optional[str]
) -> Optional[int]:
    if vendor_name is None:
        return None
    with session_scope(connection_or_session) as session:
        vendor_id = session.scalar(
            select(db_schema.Vendor.id).where(db_schema.Vendor.name == vendor_name)
        )
    if vendor_id is None:
        raise sqlite3.IntegrityError("Vendor name does not exist.")
    return int(vendor_id)


def create_host(
    connection_or_session: sqlite3.Connection | Session,
    name: str,
    notes: Optional[str] = None,
    vendor: Optional[str] = None,
) -> Host:
    vendor_id = _resolve_vendor_id(connection_or_session, vendor)
    with write_session_scope(connection_or_session) as session:
        model = db_schema.Host(name=name, notes=notes, vendor_id=vendor_id)
        try:
            session.add(model)
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)
        session.refresh(model)
    return Host(id=int(model.id), name=name, notes=notes, vendor=vendor)


def list_hosts(connection_or_session: sqlite3.Connection | Session) -> Iterable[Host]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
                    db_schema.Host.id,
                    db_schema.Host.name,
                    db_schema.Host.notes,
                    db_schema.Vendor.name.label("vendor_name"),
                )
                .select_from(db_schema.Host)
                .join(
                    db_schema.Vendor,
                    db_schema.Vendor.id == db_schema.Host.vendor_id,
                    isouter=True,
                )
                .order_by(db_schema.Host.name)
            )
            .mappings()
            .all()
        )
    return [_row_to_host(row) for row in rows]


def get_host_by_id(
    connection_or_session: sqlite3.Connection | Session, host_id: int
) -> Optional[Host]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    db_schema.Host.id,
                    db_schema.Host.name,
                    db_schema.Host.notes,
                    db_schema.Vendor.name.label("vendor_name"),
                )
                .select_from(db_schema.Host)
                .join(
                    db_schema.Vendor,
                    db_schema.Vendor.id == db_schema.Host.vendor_id,
                    isouter=True,
                )
                .where(db_schema.Host.id == host_id)
            )
            .mappings()
            .first()
        )
    return _row_to_host(row) if row else None


def get_host_by_name(
    connection_or_session: sqlite3.Connection | Session, name: str
) -> Optional[Host]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    db_schema.Host.id,
                    db_schema.Host.name,
                    db_schema.Host.notes,
                    db_schema.Vendor.name.label("vendor_name"),
                )
                .select_from(db_schema.Host)
                .join(
                    db_schema.Vendor,
                    db_schema.Vendor.id == db_schema.Host.vendor_id,
                    isouter=True,
                )
                .where(db_schema.Host.name == name)
            )
            .mappings()
            .first()
        )
    return _row_to_host(row) if row else None


def _list_hosts_with_counts_query(limit: int | None = None, offset: int = 0):
    project_count_subquery = (
        select(func.count(distinct(db_schema.IPAsset.project_id)))
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.project_id.is_not(None),
        )
        .scalar_subquery()
    )
    project_name_subquery = (
        select(db_schema.Project.name)
        .join(db_schema.IPAsset, db_schema.Project.id == db_schema.IPAsset.project_id)
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.project_id.is_not(None),
        )
        .order_by(db_schema.Project.name)
        .limit(1)
        .scalar_subquery()
    )
    project_color_subquery = (
        select(db_schema.Project.color)
        .join(db_schema.IPAsset, db_schema.Project.id == db_schema.IPAsset.project_id)
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.project_id.is_not(None),
        )
        .order_by(db_schema.Project.name)
        .limit(1)
        .scalar_subquery()
    )
    ip_count_subquery = (
        select(func.count())
        .select_from(db_schema.IPAsset)
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
        )
        .scalar_subquery()
    )
    os_ips_subquery = (
        select(func.group_concat(db_schema.IPAsset.ip_address, ", "))
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.type == IPAssetType.OS.value,
        )
        .order_by(db_schema.IPAsset.ip_address)
        .scalar_subquery()
    )
    bmc_ips_subquery = (
        select(func.group_concat(db_schema.IPAsset.ip_address, ", "))
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.type == IPAssetType.BMC.value,
        )
        .order_by(db_schema.IPAsset.ip_address)
        .scalar_subquery()
    )
    statement = (
        select(
            db_schema.Host.id.label("id"),
            db_schema.Host.name.label("name"),
            db_schema.Host.notes.label("notes"),
            db_schema.Vendor.name.label("vendor"),
            project_count_subquery.label("project_count"),
            project_name_subquery.label("project_name"),
            project_color_subquery.label("project_color"),
            ip_count_subquery.label("ip_count"),
            os_ips_subquery.label("os_ips"),
            bmc_ips_subquery.label("bmc_ips"),
        )
        .select_from(db_schema.Host)
        .join(
            db_schema.Vendor,
            db_schema.Vendor.id == db_schema.Host.vendor_id,
            isouter=True,
        )
        .order_by(db_schema.Host.name)
    )
    if limit is not None:
        statement = statement.limit(limit).offset(offset)
    return statement


def list_hosts_with_ip_counts(
    connection_or_session: sqlite3.Connection | Session,
) -> list[dict[str, object]]:
    with session_scope(connection_or_session) as session:
        rows = session.execute(_list_hosts_with_counts_query()).mappings().all()
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "notes": row["notes"],
            "vendor": row["vendor"],
            "project_count": int(row["project_count"] or 0),
            "project_name": row["project_name"] or "",
            "project_color": row["project_color"] or "",
            "ip_count": int(row["ip_count"] or 0),
            "os_ips": row["os_ips"] or "",
            "bmc_ips": row["bmc_ips"] or "",
        }
        for row in rows
    ]


def count_hosts(connection_or_session: sqlite3.Connection | Session) -> int:
    with session_scope(connection_or_session) as session:
        total = session.scalar(select(func.count()).select_from(db_schema.Host))
    return int(total or 0)


def list_hosts_with_ip_counts_paginated(
    connection_or_session: sqlite3.Connection | Session,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(_list_hosts_with_counts_query(limit=limit, offset=offset))
            .mappings()
            .all()
        )
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "notes": row["notes"],
            "vendor": row["vendor"],
            "project_count": int(row["project_count"] or 0),
            "project_name": row["project_name"] or "",
            "project_color": row["project_color"] or "",
            "ip_count": int(row["ip_count"] or 0),
            "os_ips": row["os_ips"] or "",
            "bmc_ips": row["bmc_ips"] or "",
        }
        for row in rows
    ]


def get_host_linked_assets_grouped(
    connection_or_session: sqlite3.Connection | Session, host_id: int
) -> dict[str, list[IPAsset]]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
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
                .where(
                    db_schema.IPAsset.host_id == host_id,
                    db_schema.IPAsset.archived == 0,
                )
                .order_by(db_schema.IPAsset.ip_address)
            )
            .mappings()
            .all()
        )
    assets = [_row_to_ip_asset(row) for row in rows]
    return {
        "os": [a for a in assets if a.asset_type == IPAssetType.OS],
        "bmc": [a for a in assets if a.asset_type == IPAssetType.BMC],
        "other": [
            a for a in assets if a.asset_type not in (IPAssetType.OS, IPAssetType.BMC)
        ],
    }


def list_host_pair_ips_for_hosts(
    connection_or_session: sqlite3.Connection | Session,
    host_ids: Iterable[int],
) -> dict[int, dict[str, list[str]]]:
    host_ids_list = sorted({host_id for host_id in host_ids if host_id is not None})
    if not host_ids_list:
        return {}
    with session_scope(connection_or_session) as session:
        rows = session.execute(
            select(
                db_schema.IPAsset.host_id,
                db_schema.IPAsset.type,
                db_schema.IPAsset.ip_address,
            )
            .where(
                db_schema.IPAsset.archived == 0,
                db_schema.IPAsset.host_id.in_(host_ids_list),
                db_schema.IPAsset.type.in_(
                    [IPAssetType.OS.value, IPAssetType.BMC.value]
                ),
            )
            .order_by(
                db_schema.IPAsset.host_id,
                db_schema.IPAsset.type,
                db_schema.IPAsset.ip_address,
            )
        ).all()
    mapping: dict[int, dict[str, list[str]]] = {
        host_id: {"OS": [], "BMC": []} for host_id in host_ids_list
    }
    for host_id, asset_type, ip_address in rows:
        mapping.setdefault(int(host_id), {"OS": [], "BMC": []})[str(asset_type)].append(
            str(ip_address)
        )
    return mapping


def update_host(
    connection_or_session: sqlite3.Connection | Session,
    host_id: int,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    vendor: Optional[str] = None,
) -> Optional[Host]:
    vendor_id = _resolve_vendor_id(connection_or_session, vendor)
    with write_session_scope(connection_or_session) as session:
        values: dict[str, object] = {"updated_at": func.current_timestamp()}
        if name is not None:
            values["name"] = name
        if notes is not None:
            values["notes"] = notes
        if vendor is not None:
            values["vendor_id"] = vendor_id
        try:
            session.execute(
                update(db_schema.Host)
                .where(db_schema.Host.id == host_id)
                .values(**values)
            )
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)
    return get_host_by_id(connection_or_session, host_id)


def delete_host(
    connection_or_session: sqlite3.Connection | Session, host_id: int
) -> bool:
    with write_session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.IPAsset)
            .where(db_schema.IPAsset.host_id == host_id)
            .values(host_id=None, updated_at=func.current_timestamp())
        )
        result = session.execute(
            delete(db_schema.Host).where(db_schema.Host.id == host_id)
        )
        session.commit()
    return bool(result.rowcount)
