from __future__ import annotations

import sqlite3
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAssetType

from ._db import session_scope

CompletionKind = Literal["incomplete", "complete"]


def _has_active_asset(asset_type: IPAssetType):
    return (
        select(db_schema.IPAsset.id)
        .where(
            db_schema.IPAsset.host_id == db_schema.Host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.type == asset_type.value,
        )
        .exists()
    )


def list_host_completion_records(
    connection_or_session: sqlite3.Connection | Session,
    *,
    kind: CompletionKind,
    limit: int,
    after_host_id: Optional[int] = None,
    missing_type: Optional[IPAssetType] = None,
) -> list[dict[str, object]]:
    """Return complete or one-sided OS/BMC Hosts in stable Host-ID order."""

    has_os = _has_active_asset(IPAssetType.OS)
    has_bmc = _has_active_asset(IPAssetType.BMC)
    statement = select(db_schema.Host.id)

    if kind == "complete":
        statement = statement.where(has_os, has_bmc)
    elif missing_type == IPAssetType.OS:
        statement = statement.where(~has_os, has_bmc)
    elif missing_type == IPAssetType.BMC:
        statement = statement.where(has_os, ~has_bmc)
    else:
        statement = statement.where((has_os & ~has_bmc) | (~has_os & has_bmc))

    if after_host_id is not None:
        statement = statement.where(db_schema.Host.id > after_host_id)
    statement = statement.order_by(db_schema.Host.id).limit(limit)

    with session_scope(connection_or_session) as session:
        host_ids = [int(value) for value in session.scalars(statement).all()]
        if not host_ids:
            return []

        host_rows = (
            session.execute(
                select(
                    db_schema.Host.id,
                    db_schema.Host.name,
                    db_schema.Vendor.name.label("vendor_name"),
                )
                .select_from(db_schema.Host)
                .join(
                    db_schema.Vendor,
                    db_schema.Vendor.id == db_schema.Host.vendor_id,
                    isouter=True,
                )
                .where(db_schema.Host.id.in_(host_ids))
                .order_by(db_schema.Host.id)
            )
            .mappings()
            .all()
        )
        asset_rows = (
            session.execute(
                select(
                    db_schema.IPAsset.id,
                    db_schema.IPAsset.host_id,
                    db_schema.IPAsset.ip_address,
                    db_schema.IPAsset.type,
                    db_schema.IPAsset.project_id,
                    db_schema.Project.name.label("project_name"),
                )
                .select_from(db_schema.IPAsset)
                .join(
                    db_schema.Project,
                    db_schema.Project.id == db_schema.IPAsset.project_id,
                    isouter=True,
                )
                .where(
                    db_schema.IPAsset.host_id.in_(host_ids),
                    db_schema.IPAsset.archived == 0,
                    db_schema.IPAsset.type.in_(
                        [IPAssetType.OS.value, IPAssetType.BMC.value]
                    ),
                )
                .order_by(
                    db_schema.IPAsset.host_id,
                    db_schema.IPAsset.type,
                    db_schema.IPAsset.ip_address,
                )
            )
            .mappings()
            .all()
        )

    records: dict[int, dict[str, object]] = {
        int(row["id"]): {
            "host_id": int(row["id"]),
            "host_name": str(row["name"]),
            "vendor": row["vendor_name"],
            "os_assets": [],
            "bmc_assets": [],
        }
        for row in host_rows
    }
    for row in asset_rows:
        host_id = int(row["host_id"])
        key = "os_assets" if row["type"] == IPAssetType.OS.value else "bmc_assets"
        assets = records[host_id][key]
        assert isinstance(assets, list)
        assets.append(
            {
                "id": int(row["id"]),
                "ip_address": str(row["ip_address"]),
                "project_id": (
                    int(row["project_id"]) if row["project_id"] is not None else None
                ),
                "project_name": row["project_name"],
            }
        )
    return [records[host_id] for host_id in host_ids]
