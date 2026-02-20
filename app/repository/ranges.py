from __future__ import annotations

import ipaddress
import sqlite3
from typing import Iterable, Optional

from sqlalchemy import func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAssetType, IPRange
from app.utils import DEFAULT_PROJECT_COLOR, normalize_cidr, parse_ipv4_network

from ._asset_tags import list_tag_details_for_ip_assets
from ._db import (
    reraise_as_sqlite_integrity_error,
    session_scope,
    write_session_scope,
)
from .hosts import list_host_pair_ips_for_hosts
from .mappers import _row_to_ip_range


def create_ip_range(
    connection_or_session: sqlite3.Connection | Session,
    name: str,
    cidr: str,
    notes: Optional[str] = None,
) -> IPRange:
    normalized_cidr = normalize_cidr(cidr)
    with write_session_scope(connection_or_session) as session:
        model = db_schema.IPRange(name=name, cidr=normalized_cidr, notes=notes)
        try:
            session.add(model)
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)
        session.refresh(model)
        row = {
            "id": model.id,
            "name": model.name,
            "cidr": model.cidr,
            "notes": model.notes,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }
    return _row_to_ip_range(row)


def list_ip_ranges(
    connection_or_session: sqlite3.Connection | Session,
) -> Iterable[IPRange]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
                    db_schema.IPRange.id,
                    db_schema.IPRange.name,
                    db_schema.IPRange.cidr,
                    db_schema.IPRange.notes,
                    db_schema.IPRange.created_at,
                    db_schema.IPRange.updated_at,
                ).order_by(db_schema.IPRange.name)
            )
            .mappings()
            .all()
        )
    return [_row_to_ip_range(row) for row in rows]


def get_ip_range_by_id(
    connection_or_session: sqlite3.Connection | Session, range_id: int
) -> IPRange | None:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    db_schema.IPRange.id,
                    db_schema.IPRange.name,
                    db_schema.IPRange.cidr,
                    db_schema.IPRange.notes,
                    db_schema.IPRange.created_at,
                    db_schema.IPRange.updated_at,
                ).where(db_schema.IPRange.id == range_id)
            )
            .mappings()
            .first()
        )
    if row is None:
        return None
    return _row_to_ip_range(row)


def update_ip_range(
    connection_or_session: sqlite3.Connection | Session,
    range_id: int,
    name: str,
    cidr: str,
    notes: Optional[str] = None,
) -> IPRange | None:
    normalized_cidr = normalize_cidr(cidr)
    with write_session_scope(connection_or_session) as session:
        try:
            session.execute(
                update(db_schema.IPRange)
                .where(db_schema.IPRange.id == range_id)
                .values(
                    name=name,
                    cidr=normalized_cidr,
                    notes=notes,
                    updated_at=func.current_timestamp(),
                )
            )
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)
    return get_ip_range_by_id(connection_or_session, range_id)


def delete_ip_range(
    connection_or_session: sqlite3.Connection | Session, range_id: int
) -> bool:
    with write_session_scope(connection_or_session) as session:
        result = session.execute(
            delete(db_schema.IPRange).where(db_schema.IPRange.id == range_id)
        )
        session.commit()
    return bool(result.rowcount)


def _total_usable_addresses(network: ipaddress.IPv4Network) -> int:
    if network.prefixlen == 32:
        return 1
    if network.prefixlen == 31:
        return 2
    return max(int(network.num_addresses) - 2, 0)


def get_ip_range_utilization(
    connection_or_session: sqlite3.Connection | Session,
) -> list[dict[str, object]]:
    ranges = list(list_ip_ranges(connection_or_session))
    utilization: list[dict[str, object]] = []
    with session_scope(connection_or_session) as session:
        for ip_range in ranges:
            network = parse_ipv4_network(ip_range.cidr)
            total = int(network.num_addresses)
            total_usable = _total_usable_addresses(network)
            start_ip = int(network.network_address)
            end_ip = int(network.broadcast_address)
            used = int(
                session.scalar(
                    select(func.count(func.distinct(db_schema.IPAsset.ip_int))).where(
                        db_schema.IPAsset.archived == 0,
                        db_schema.IPAsset.ip_int.is_not(None),
                        db_schema.IPAsset.ip_int >= start_ip,
                        db_schema.IPAsset.ip_int <= end_ip,
                    )
                )
                or 0
            )
            free = max(total_usable - used, 0)
            utilization_percent = (used / total_usable * 100.0) if total_usable else 0.0
            utilization.append(
                {
                    "id": ip_range.id,
                    "name": ip_range.name,
                    "cidr": ip_range.cidr,
                    "notes": ip_range.notes,
                    "total": total,
                    "total_usable": total_usable,
                    "used": used,
                    "free": free,
                    "utilization_percent": utilization_percent,
                }
            )
    return utilization


def get_ip_range_address_breakdown(
    connection_or_session: sqlite3.Connection | Session,
    range_id: int,
) -> dict[str, object] | None:
    ip_range = get_ip_range_by_id(connection_or_session, range_id)
    if ip_range is None:
        return None

    network = parse_ipv4_network(ip_range.cidr)
    start_ip = int(network.network_address)
    end_ip = int(network.broadcast_address)
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
                    db_schema.IPAsset.id.label("asset_id"),
                    db_schema.IPAsset.ip_address.label("ip_address"),
                    db_schema.IPAsset.ip_int.label("ip_int"),
                    db_schema.IPAsset.type.label("asset_type"),
                    db_schema.IPAsset.host_id.label("host_id"),
                    db_schema.IPAsset.project_id.label("project_id"),
                    db_schema.IPAsset.notes.label("notes"),
                    db_schema.Project.name.label("project_name"),
                    db_schema.Project.color.label("project_color"),
                )
                .select_from(db_schema.IPAsset)
                .join(
                    db_schema.Project,
                    db_schema.Project.id == db_schema.IPAsset.project_id,
                    isouter=True,
                )
                .where(
                    db_schema.IPAsset.archived == 0,
                    db_schema.IPAsset.ip_int.is_not(None),
                    db_schema.IPAsset.ip_int >= start_ip,
                    db_schema.IPAsset.ip_int <= end_ip,
                )
            )
            .mappings()
            .all()
        )

    used_entries: list[dict[str, object]] = []
    used_addresses: set[ipaddress.IPv4Address] = set()
    used_asset_ids: list[int] = []
    used_host_ids: list[int] = []
    for row in rows:
        ip_value = ipaddress.IPv4Address(int(row["ip_int"]))
        used_addresses.add(ip_value)
        used_asset_ids.append(int(row["asset_id"]))
        if row["host_id"]:
            used_host_ids.append(int(row["host_id"]))
        used_entries.append(
            {
                "ip_address": str(ip_value),
                "sort_ip_int": int(row["ip_int"]),
                "status": "used",
                "asset_id": row["asset_id"],
                "host_id": row["host_id"],
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "project_color": row["project_color"] or DEFAULT_PROJECT_COLOR,
                "project_unassigned": not row["project_name"],
                "asset_type": row["asset_type"],
                "notes": row["notes"] or "",
                "host_pair": "",
                "tags": [],
            }
        )

    tag_map = list_tag_details_for_ip_assets(connection_or_session, used_asset_ids)
    for entry in used_entries:
        entry["tags"] = tag_map.get(int(entry["asset_id"]), [])
    host_pair_lookup = list_host_pair_ips_for_hosts(
        connection_or_session, used_host_ids
    )
    for entry in used_entries:
        host_id = entry.get("host_id")
        asset_type = entry.get("asset_type")
        if host_id and asset_type in (IPAssetType.OS.value, IPAssetType.BMC.value):
            pair_type = (
                IPAssetType.BMC.value
                if asset_type == IPAssetType.OS.value
                else IPAssetType.OS.value
            )
            entry["host_pair"] = ", ".join(
                host_pair_lookup.get(int(host_id), {}).get(pair_type, [])
            )

    used_sorted = sorted(
        used_entries,
        key=lambda entry: int(entry["sort_ip_int"]),
    )
    usable_addresses = list(network.hosts())
    free_entries = [
        {
            "ip_address": str(ip_value),
            "sort_ip_int": int(ip_value),
            "status": "free",
            "asset_id": None,
            "project_id": None,
            "project_name": None,
            "project_color": DEFAULT_PROJECT_COLOR,
            "project_unassigned": True,
            "asset_type": None,
            "notes": "",
            "host_pair": "",
            "tags": [],
        }
        for ip_value in usable_addresses
        if ip_value not in used_addresses
    ]
    address_entries = sorted(
        [*used_sorted, *free_entries],
        key=lambda entry: int(entry["sort_ip_int"]),
    )
    for entry in address_entries:
        entry.pop("sort_ip_int", None)

    return {
        "ip_range": ip_range,
        "addresses": address_entries,
        "used": len(used_sorted),
        "free": len(free_entries),
        "total_usable": len(usable_addresses),
    }
