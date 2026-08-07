from __future__ import annotations

import sqlite3
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import IPAssetType

from ._db import session_scope

CompletionKind = Literal["incomplete", "complete"]


def get_host_completion_engine_source(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, object]:
    """Return one consistent inventory snapshot for deterministic completion."""

    with session_scope(connection_or_session) as session:
        hosts = [
            {"id": int(row["id"]), "name": str(row["name"])}
            for row in session.execute(
                select(db_schema.Host.id, db_schema.Host.name).order_by(
                    db_schema.Host.id
                )
            )
            .mappings()
            .all()
        ]
        assets = [
            {
                "id": int(row["id"]),
                "host_id": int(row["host_id"]) if row["host_id"] is not None else None,
                "ip_address": str(row["ip_address"]),
                "type": str(row["type"]) if row["type"] is not None else None,
            }
            for row in session.execute(
                select(
                    db_schema.IPAsset.id,
                    db_schema.IPAsset.host_id,
                    db_schema.IPAsset.ip_address,
                    db_schema.IPAsset.type,
                )
                .where(db_schema.IPAsset.archived == 0)
                .order_by(db_schema.IPAsset.id)
            )
            .mappings()
            .all()
        ]
        decisions = [
            {
                "id": int(row["id"]),
                "case_type": str(row["case_type"]),
                "host_id": int(row["host_id"]) if row["host_id"] is not None else None,
                "mode": str(row["mode"]),
                "os_address": row["os_address"],
                "bmc_address": row["bmc_address"],
                "candidate_ip": row["candidate_ip"],
                "corrected_ip": row["corrected_ip"],
                "decision": str(row["decision"]),
                "target_host_id": (
                    int(row["target_host_id"])
                    if row["target_host_id"] is not None
                    else None
                ),
                "host_name": row["host_name"],
            }
            for row in session.execute(
                select(
                    db_schema.HostCompletionDecision.id,
                    db_schema.HostCompletionDecision.case_type,
                    db_schema.HostCompletionDecision.host_id,
                    db_schema.HostCompletionDecision.mode,
                    db_schema.HostCompletionDecision.os_address,
                    db_schema.HostCompletionDecision.bmc_address,
                    db_schema.HostCompletionDecision.candidate_ip,
                    db_schema.HostCompletionDecision.corrected_ip,
                    db_schema.HostCompletionDecision.decision,
                    db_schema.HostCompletionDecision.target_host_id,
                    db_schema.HostCompletionDecision.host_name,
                ).order_by(db_schema.HostCompletionDecision.id)
            )
            .mappings()
            .all()
        ]
    return {"hosts": hosts, "assets": assets, "decisions": decisions}


def get_host_reconciliation_snapshot(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, object]:
    """Return authoritative inventory facts for the read-only agent engine."""

    with session_scope(connection_or_session) as session:
        hosts = [
            {"id": int(row["id"]), "name": str(row["name"])}
            for row in session.execute(
                select(db_schema.Host.id, db_schema.Host.name).order_by(
                    db_schema.Host.id
                )
            )
            .mappings()
            .all()
        ]
        assets = [
            {
                "id": int(row["id"]),
                "host_id": int(row["host_id"]) if row["host_id"] is not None else None,
                "ip_address": str(row["ip_address"]),
                "type": str(row["type"]) if row["type"] is not None else None,
                "archived": bool(row["archived"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in session.execute(
                select(
                    db_schema.IPAsset.id,
                    db_schema.IPAsset.host_id,
                    db_schema.IPAsset.ip_address,
                    db_schema.IPAsset.type,
                    db_schema.IPAsset.archived,
                    db_schema.IPAsset.updated_at,
                ).order_by(db_schema.IPAsset.id)
            )
            .mappings()
            .all()
        ]
        decisions = [
            {
                "id": int(row["id"]),
                "case_type": str(row["case_type"]),
                "host_id": int(row["host_id"]) if row["host_id"] is not None else None,
                "os_address": row["os_address"],
                "bmc_address": row["bmc_address"],
                "candidate_ip": row["candidate_ip"],
                "decision": str(row["decision"]),
                "target_host_id": (
                    int(row["target_host_id"])
                    if row["target_host_id"] is not None
                    else None
                ),
                "proposal_id": row["proposal_id"],
                "inventory_fingerprint": row["inventory_fingerprint"],
                "idempotency_key": row["idempotency_key"],
            }
            for row in session.execute(
                select(
                    db_schema.HostCompletionDecision.id,
                    db_schema.HostCompletionDecision.case_type,
                    db_schema.HostCompletionDecision.host_id,
                    db_schema.HostCompletionDecision.os_address,
                    db_schema.HostCompletionDecision.bmc_address,
                    db_schema.HostCompletionDecision.candidate_ip,
                    db_schema.HostCompletionDecision.decision,
                    db_schema.HostCompletionDecision.target_host_id,
                    db_schema.HostCompletionDecision.proposal_id,
                    db_schema.HostCompletionDecision.inventory_fingerprint,
                    db_schema.HostCompletionDecision.idempotency_key,
                ).order_by(db_schema.HostCompletionDecision.id)
            )
            .mappings()
            .all()
        ]
    return {"hosts": hosts, "assets": assets, "decisions": decisions}


def create_host_completion_decision(
    connection_or_session: sqlite3.Connection | Session,
    *,
    case_type: str,
    host_id: int | None,
    mode: str,
    os_address: str | None,
    bmc_address: str | None,
    candidate_ip: str | None,
    corrected_ip: str | None,
    decision: str,
    target_host_id: int | None,
    host_name: str | None,
    decided_by: int,
    proposal_id: str | None = None,
    inventory_fingerprint: str | None = None,
    idempotency_key: str | None = None,
) -> int:
    from ._db import write_session_scope

    with write_session_scope(connection_or_session) as session:
        model = db_schema.HostCompletionDecision(
            case_type=case_type,
            host_id=host_id,
            mode=mode,
            os_address=os_address,
            bmc_address=bmc_address,
            candidate_ip=candidate_ip,
            corrected_ip=corrected_ip,
            decision=decision,
            target_host_id=target_host_id,
            host_name=host_name,
            decided_by=decided_by,
            proposal_id=proposal_id,
            inventory_fingerprint=inventory_fingerprint,
            idempotency_key=idempotency_key,
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        return int(model.id)


def get_host_completion_analytics_source(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, object]:
    """Return the active inventory fields needed for completion analytics."""

    with session_scope(connection_or_session) as session:
        host_ids = [
            int(value)
            for value in session.scalars(
                select(db_schema.Host.id).order_by(db_schema.Host.id)
            ).all()
        ]
        assets = [
            {
                "host_id": (
                    int(row["host_id"]) if row["host_id"] is not None else None
                ),
                "ip_address": str(row["ip_address"]),
                "type": row["type"],
            }
            for row in session.execute(
                select(
                    db_schema.IPAsset.host_id,
                    db_schema.IPAsset.ip_address,
                    db_schema.IPAsset.type,
                )
                .where(db_schema.IPAsset.archived == 0)
                .order_by(db_schema.IPAsset.id)
            )
            .mappings()
            .all()
        ]

    return {"host_ids": host_ids, "assets": assets}


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
