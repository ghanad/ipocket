"""ipocket adapter for the deterministic, read-only reconciliation agent.

The agent receives an inventory projection and returns findings.  All writes
remain in this ipocket-owned application service and use one database
transaction, including audit entries and the operator decision.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import sqlite3
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import repository, schema as db_schema
from app.dependencies import create_db_session
from app.repository._db import write_session_scope as _write_scope
from app.utils import ipv4_to_int
from ipocket_agent import (
    AgentDecision,
    Asset,
    Host,
    Inventory,
    Rule,
    Transformation,
    reconcile,
)


Decision = Literal[
    "ACCEPT",
    "CORRECT",
    "WRONG_PAIR",
    "UNSURE",
    "EXCEPTION",
    "ATTACH_EXISTING",
    "DEACTIVATE",
]


class ReconciliationError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _db_path(connection: sqlite3.Connection) -> str | None:
    row = connection.execute("PRAGMA database_list").fetchone()
    return str(row[2]) if row and row[2] else None


def _min_support() -> int:
    try:
        return max(1, int(os.getenv("IPOCKET_HOST_COMPLETION_MIN_SUPPORT", "3")))
    except ValueError:
        return 3


def _host_name_template() -> str:
    return "server_{bmc}"


def _to_inventory(source: dict[str, object]) -> Inventory:
    raw_assets = source.get("assets", [])
    raw_hosts = source.get("hosts", [])
    raw_decisions = source.get("decisions", [])
    assert isinstance(raw_assets, list)
    assert isinstance(raw_hosts, list)
    assert isinstance(raw_decisions, list)

    assets = tuple(
        Asset(
            id=str(item["id"]),
            ip_address=str(item["ip_address"]),
            asset_type=str(item["type"]),  # type: ignore[arg-type]
            host_id=str(item["host_id"]) if item.get("host_id") is not None else None,
            archived=bool(item.get("archived")),
        )
        for item in raw_assets
        if isinstance(item, dict)
        and item.get("type") in {"OS", "BMC", "VM", "VIP", "OTHER"}
    )
    hosts = tuple(
        Host(id=str(item["id"]), name=str(item["name"]))
        for item in raw_hosts
        if isinstance(item, dict)
    )
    asset_by_ip = {asset.ip_address: asset for asset in assets}
    decisions: list[AgentDecision] = []
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("decision") or "")
        if kind in {"REJECT", "WRONG_PAIR"}:
            os_ip = item.get("os_address")
            bmc_ip = item.get("bmc_address") or item.get("candidate_ip")
            if os_ip and bmc_ip:
                decisions.append(
                    AgentDecision(
                        kind="WRONG_PAIR", os_ip=str(os_ip), bmc_ip=str(bmc_ip)
                    )
                )
        elif kind == "UNSURE":
            for address in (item.get("os_address"), item.get("bmc_address")):
                asset = asset_by_ip.get(str(address)) if address else None
                if asset is not None:
                    decisions.append(AgentDecision(kind="UNSURE", asset_id=asset.id))
        elif kind in {"EXCEPTION", "NO_BMC", "NO_OS"}:
            for address in (item.get("os_address"), item.get("bmc_address")):
                asset = asset_by_ip.get(str(address)) if address else None
                if asset is not None:
                    decisions.append(AgentDecision(kind="EXCEPTION", asset_id=asset.id))
    return Inventory(assets=assets, hosts=hosts, decisions=tuple(decisions))


def _result(connection_or_session):
    source = repository.get_host_reconciliation_snapshot(connection_or_session)
    inventory = _to_inventory(source)
    return inventory, reconcile(
        inventory,
        min_support=_min_support(),
        host_name_template=_host_name_template(),
        manual_rules=_manual_rules(source),
    )


def _manual_rules(source: dict[str, object]) -> tuple[Rule, ...]:
    raw_rules = source.get("manual_rules", [])
    assert isinstance(raw_rules, list)
    rules: list[Rule] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        prefix_length = int(item["prefix_length"])
        source_prefix = str(item["source_prefix"])
        target_prefix = str(item["target_prefix"])
        rules.append(
            Rule(
                id=f"manual-{item['id']}",
                transformation=Transformation(
                    kind="PREFIX_16" if prefix_length == 16 else "PREFIX_24",
                    source=source_prefix,
                    target=target_prefix,
                ),
                support=0,
                contradictions=0,
                active=bool(item["active"]),
                strength="STRONG" if bool(item["active"]) else "INACTIVE",
            )
        )
    return tuple(rules)


def _manual_rule_payload(model: db_schema.HostCompletionManualRule) -> dict[str, object]:
    return {
        "id": model.id,
        "source_prefix": model.source_prefix,
        "target_prefix": model.target_prefix,
        "prefix_length": model.prefix_length,
        "active": bool(model.active),
        "notes": model.notes,
    }


def _normalize_manual_rule(
    source_prefix: str, target_prefix: str
) -> tuple[str, str, int]:
    try:
        source = ipaddress.ip_network(source_prefix.strip(), strict=True)
        target = ipaddress.ip_network(target_prefix.strip(), strict=True)
    except ValueError as exc:
        raise ReconciliationError(
            422, "Source and target must be valid IPv4 network prefixes."
        ) from exc
    if source.version != 4 or target.version != 4:
        raise ReconciliationError(422, "Source and target must be IPv4 network prefixes.")
    if source.prefixlen not in {16, 24} or target.prefixlen != source.prefixlen:
        raise ReconciliationError(
            422, "Source and target must use the same /16 or /24 prefix length."
        )
    if source == target:
        raise ReconciliationError(422, "Source and target prefixes must differ.")
    return str(source), str(target), source.prefixlen


def create_manual_rule(
    connection_or_session,
    *,
    source_prefix: str,
    target_prefix: str,
    active: bool,
    notes: str | None,
    user,
) -> dict[str, object]:
    source, target, prefix_length = _normalize_manual_rule(source_prefix, target_prefix)
    with _write_scope(connection_or_session) as session:
        existing = session.scalar(
            select(db_schema.HostCompletionManualRule).where(
                db_schema.HostCompletionManualRule.source_prefix == source,
                db_schema.HostCompletionManualRule.target_prefix == target,
                db_schema.HostCompletionManualRule.prefix_length == prefix_length,
            )
        )
        if existing is not None:
            raise ReconciliationError(409, "This manual rule already exists.")
        model = db_schema.HostCompletionManualRule(
            source_prefix=source,
            target_prefix=target,
            prefix_length=prefix_length,
            active=int(active),
            notes=notes.strip() if notes and notes.strip() else None,
            created_by=user.id,
        )
        session.add(model)
        session.flush()
        _audit(
            session,
            user=user,
            target_type="HOST_COMPLETION_RULE",
            target_id=model.id,
            label=f"{source} -> {target}",
            changes=f"Created manual rule (active={int(active)}).",
            action="CREATE",
        )
        session.commit()
        return _manual_rule_payload(model)


def update_manual_rule(
    connection_or_session,
    *,
    rule_id: int,
    source_prefix: str,
    target_prefix: str,
    active: bool,
    notes: str | None,
    user,
) -> dict[str, object]:
    source, target, prefix_length = _normalize_manual_rule(source_prefix, target_prefix)
    with _write_scope(connection_or_session) as session:
        model = session.get(db_schema.HostCompletionManualRule, rule_id)
        if model is None:
            raise ReconciliationError(404, "Manual rule was not found.")
        duplicate = session.scalar(
            select(db_schema.HostCompletionManualRule).where(
                db_schema.HostCompletionManualRule.source_prefix == source,
                db_schema.HostCompletionManualRule.target_prefix == target,
                db_schema.HostCompletionManualRule.prefix_length == prefix_length,
                db_schema.HostCompletionManualRule.id != rule_id,
            )
        )
        if duplicate is not None:
            raise ReconciliationError(409, "This manual rule already exists.")
        before = _manual_rule_payload(model)
        model.source_prefix = source
        model.target_prefix = target
        model.prefix_length = prefix_length
        model.active = int(active)
        model.notes = notes.strip() if notes and notes.strip() else None
        model.updated_at = func.current_timestamp()
        session.flush()
        _audit(
            session,
            user=user,
            target_type="HOST_COMPLETION_RULE",
            target_id=model.id,
            label=f"{source} -> {target}",
            changes=(
                f"Updated manual rule from {before['source_prefix']} -> "
                f"{before['target_prefix']} (active={int(bool(before['active']))}) "
                f"to active={int(active)}."
            ),
        )
        session.commit()
        return _manual_rule_payload(model)


def _serialize_finding(finding, inventory: Inventory) -> dict[str, object]:
    asset_by_id = {asset.id: asset for asset in inventory.assets}
    assets = [asset_by_id[asset_id] for asset_id in finding.asset_ids]
    return {
        "finding_type": finding.kind,
        "state": "CONFLICT"
        if finding.kind == "CONFLICT"
        else ("UNMATCHED" if finding.kind == "UNMATCHED_ASSET" else "PROPOSED"),
        "proposal_id": finding.proposal_id,
        "inventory_fingerprint": finding.inventory_fingerprint,
        "host_id": int(finding.host_id) if finding.host_id is not None else None,
        "proposed_host_name": finding.proposed_host_name,
        "assets": [
            {
                "id": int(asset.id),
                "ip_address": asset.ip_address,
                "type": asset.asset_type,
                "host_id": int(asset.host_id) if asset.host_id is not None else None,
            }
            for asset in assets
        ],
        "candidate_ips": list(finding.candidate_ips),
        "match_strength": finding.strength,
        "evidence": list(finding.evidence),
        "reasons": list(finding.reasons),
        "rule_ids": list(finding.rule_ids),
    }


def list_findings(connection_or_session) -> dict[str, object]:
    inventory, result = _result(connection_or_session)
    items = [_serialize_finding(finding, inventory) for finding in result.findings]
    return {"items": items, "total": len(items)}


def next_finding(connection_or_session) -> dict[str, object]:
    payload = list_findings(connection_or_session)
    items = payload["items"]
    assert isinstance(items, list)
    return {"item": items[0] if items else None, "remaining": max(len(items) - 1, 0)}


def get_summary(connection_or_session) -> dict[str, object]:
    source = repository.get_host_reconciliation_snapshot(connection_or_session)
    inventory = _to_inventory(source)
    result = reconcile(
        inventory,
        min_support=_min_support(),
        host_name_template=_host_name_template(),
        manual_rules=_manual_rules(source),
    )
    manual_by_id = {
        f"manual-{item['id']}": item
        for item in source["manual_rules"]
        if isinstance(item, dict)
    }
    state_counts = {
        state: sum(value == state for value in result.states.values())
        for state in ("RESOLVED", "PROPOSED", "UNMATCHED", "CONFLICT", "EXCEPTION")
    }
    return {
        **result.kpis,
        "states": state_counts,
        "unexplained_active_assets": state_counts["UNMATCHED"]
        + state_counts["CONFLICT"],
        "active_assets": len(result.states),
        "rules": [
            {
                "id": rule.id,
                "direction": rule.direction,
                "transformation": rule.transformation.description,
                "source_pattern": rule.transformation.source,
                "target_pattern": rule.transformation.target,
                "strength": rule.strength,
                "active": rule.active,
                "support": rule.support,
                "contradictions": rule.contradictions,
                "examples": [
                    f"{os_ip} -> {bmc_ip}" for os_ip, bmc_ip in rule.examples[:5]
                ],
                "managed": rule.id in manual_by_id,
                "manual_rule_id": (
                    int(manual_by_id[rule.id]["id"])
                    if rule.id in manual_by_id
                    else None
                ),
                "notes": (
                    manual_by_id[rule.id]["notes"]
                    if rule.id in manual_by_id
                    else None
                ),
            }
            for rule in result.rules
        ],
        "findings": [
            _serialize_finding(finding, inventory) for finding in result.findings
        ],
    }


def _audit(
    session: Session,
    *,
    user,
    target_type: str,
    target_id: int,
    label: str,
    changes: str,
    action: str = "UPDATE",
) -> None:
    session.add(
        db_schema.AuditLog(
            user_id=user.id,
            username=user.username,
            target_type=target_type,
            target_id=target_id,
            target_label=label,
            action=action,
            changes=changes,
        )
    )


def _asset_rows(session: Session, asset_ids: tuple[str, ...]):
    ids = [int(asset_id) for asset_id in asset_ids]
    rows = session.scalars(
        select(db_schema.IPAsset).where(db_schema.IPAsset.id.in_(ids))
    ).all()
    if len(rows) != len(ids):
        raise ReconciliationError(409, "Proposal is stale; an asset no longer exists.")
    return rows


def _resolve_host(session: Session, name: str):
    host = session.scalar(
        select(db_schema.Host).where(func.lower(db_schema.Host.name) == name.lower())
    )
    if host is None:
        host = db_schema.Host(name=name)
        session.add(host)
        session.flush()
        return host, True
    return host, False


def _normalize_counterpart_ip(value: str | None) -> str:
    if not value:
        raise ReconciliationError(422, "counterpart_ip is required.")
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ReconciliationError(
            422, "counterpart_ip must be a valid IPv4 address."
        ) from exc
    if address.version != 4:
        raise ReconciliationError(422, "counterpart_ip must be a valid IPv4 address.")
    return str(address)


def _attach(session: Session, asset, host, *, user) -> None:
    if bool(asset.archived) or asset.host_id not in {None, host.id}:
        raise ReconciliationError(
            409, "Proposal is stale; an asset can no longer be attached."
        )
    session.execute(
        update(db_schema.IPAsset)
        .where(db_schema.IPAsset.id == asset.id)
        .values(host_id=host.id, updated_at=func.current_timestamp())
    )
    _audit(
        session,
        user=user,
        target_type="IP_ASSET",
        target_id=int(asset.id),
        label=str(asset.ip_address),
        changes=f"Attached to Host {host.name} by reconciliation proposal.",
    )
    _after_asset_link(asset)


def _validate_bmc_capacity(session: Session, host, assets) -> None:
    proposed_bmc_ids = {int(asset.id) for asset in assets if asset.type == "BMC"}
    if not proposed_bmc_ids:
        return
    existing_bmc_id = session.scalar(
        select(db_schema.IPAsset.id).where(
            db_schema.IPAsset.host_id == host.id,
            db_schema.IPAsset.archived == 0,
            db_schema.IPAsset.type == "BMC",
            db_schema.IPAsset.id.not_in(proposed_bmc_ids),
        )
    )
    if existing_bmc_id is not None:
        raise ReconciliationError(
            409, "Target Host already has a different active BMC asset."
        )


def _after_asset_link(_asset) -> None:
    """Test seam for verifying transaction rollback after a partial apply."""


def _idempotency_key(proposal_id: str, decision: str, supplied: str | None) -> str:
    if supplied and supplied.strip():
        return supplied.strip()[:200]
    return hashlib.sha256(f"{proposal_id}:{decision}".encode()).hexdigest()


def _existing_response(row) -> dict[str, object]:
    return {
        "id": int(row.id),
        "decision": str(row.decision),
        "host_id": int(row.target_host_id) if row.target_host_id is not None else None,
        "proposal_id": row.proposal_id,
        "idempotent_replay": True,
    }


def apply_decision(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    inventory_fingerprint: str,
    decision: Decision,
    user,
    idempotency_key: str | None = None,
    target_host_id: int | None = None,
    counterpart_ip: str | None = None,
    counterpart_type: Literal["OS", "BMC"] | None = None,
) -> dict[str, object]:
    """Validate and apply one proposal in a single ipocket-owned transaction."""

    key = _idempotency_key(proposal_id, decision, idempotency_key)
    session = create_db_session(_db_path(connection))
    # create_db_session enables SQLite foreign keys with a statement, which
    # starts SQLAlchemy's implicit transaction. Close it before the unit of work.
    session.commit()
    try:
        with session.begin():
            duplicate = session.scalar(
                select(db_schema.HostCompletionDecision).where(
                    db_schema.HostCompletionDecision.idempotency_key == key
                )
            )
            if duplicate is not None:
                if (
                    duplicate.proposal_id != proposal_id
                    or duplicate.decision != decision
                ):
                    raise ReconciliationError(
                        409, "Idempotency key was already used for another decision."
                    )
                return _existing_response(duplicate)

            inventory, result = _result(session)
            finding = next(
                (item for item in result.findings if item.proposal_id == proposal_id),
                None,
            )
            if (
                finding is None
                or finding.inventory_fingerprint != inventory_fingerprint
            ):
                raise ReconciliationError(
                    409, "Proposal is stale; refresh the reconciliation queue."
                )

            rows = _asset_rows(session, finding.asset_ids)
            by_id = {str(row.id): row for row in rows}
            host = None
            created_host = False

            if decision == "ACCEPT":
                if finding.kind == "CREATE_HOST":
                    if not finding.proposed_host_name:
                        raise ReconciliationError(409, "Proposal has no Host name.")
                    host, created_host = _resolve_host(
                        session, finding.proposed_host_name
                    )
                    _validate_bmc_capacity(session, host, rows)
                    for asset_id in finding.asset_ids:
                        _attach(session, by_id[asset_id], host, user=user)
                elif finding.kind == "COMPLETE_HOST":
                    host = session.get(db_schema.Host, int(finding.host_id or 0))
                    if host is None:
                        raise ReconciliationError(
                            409, "Proposal Host no longer exists."
                        )
                    for asset_id in finding.asset_ids:
                        asset = by_id[asset_id]
                        if asset.host_id is None:
                            _attach(session, asset, host, user=user)
                else:
                    raise ReconciliationError(
                        409, "This finding cannot be accepted automatically."
                    )
            elif decision == "CORRECT":
                if counterpart_type not in {"OS", "BMC"}:
                    raise ReconciliationError(
                        422, "counterpart_type must be OS or BMC."
                    )
                normalized_ip = _normalize_counterpart_ip(counterpart_ip)
                corrected = session.scalar(
                    select(db_schema.IPAsset).where(
                        db_schema.IPAsset.ip_address == normalized_ip
                    )
                )
                if corrected is not None and bool(corrected.archived):
                    raise ReconciliationError(
                        409,
                        "Counterpart asset is archived and cannot be linked automatically.",
                    )
                if corrected is not None and corrected.type != counterpart_type:
                    raise ReconciliationError(
                        409,
                        f"Counterpart exists as {corrected.type or 'untyped'}, not {counterpart_type}.",
                    )
                base = next(
                    (
                        row
                        for row in rows
                        if row.type in {"OS", "BMC"} and row.type != counterpart_type
                    ),
                    None,
                )
                if base is None:
                    raise ReconciliationError(
                        422, "Correction must pair one OS and one BMC asset."
                    )
                if corrected is None:
                    corrected = db_schema.IPAsset(
                        ip_address=normalized_ip,
                        ip_int=ipv4_to_int(normalized_ip),
                        type=counterpart_type,
                        archived=0,
                    )
                    session.add(corrected)
                    session.flush()
                    session.add(
                        db_schema.AuditLog(
                            user_id=user.id,
                            username=user.username,
                            target_type="IP_ASSET",
                            target_id=int(corrected.id),
                            target_label=normalized_ip,
                            action="CREATE",
                            changes=(
                                f"Created {counterpart_type} asset from operator-supplied "
                                "reconciliation counterpart."
                            ),
                        )
                    )
                if finding.host_id is not None:
                    host = session.get(db_schema.Host, int(finding.host_id))
                elif corrected.host_id is not None:
                    host = session.get(db_schema.Host, int(corrected.host_id))
                elif base.host_id is not None:
                    host = session.get(db_schema.Host, int(base.host_id))
                else:
                    bmc = corrected if counterpart_type == "BMC" else base
                    host, created_host = _resolve_host(
                        session, _host_name_template().format(bmc=bmc.ip_address)
                    )
                if host is None:
                    raise ReconciliationError(409, "Target Host no longer exists.")
                if any(
                    asset.host_id not in {None, host.id} for asset in (base, corrected)
                ):
                    raise ReconciliationError(
                        409, "An asset is already attached to a different Host."
                    )
                _validate_bmc_capacity(session, host, (base, corrected))
                for asset in (base, corrected):
                    if asset.host_id is None:
                        _attach(session, asset, host, user=user)
            elif decision == "ATTACH_EXISTING":
                if target_host_id is None:
                    raise ReconciliationError(422, "target_host_id is required.")
                host = session.get(db_schema.Host, target_host_id)
                if host is None:
                    raise ReconciliationError(404, "Target Host not found.")
                if any(asset.host_id not in {None, target_host_id} for asset in rows):
                    raise ReconciliationError(
                        409, "A finding asset is attached to a different Host."
                    )
                _validate_bmc_capacity(session, host, rows)
                for asset in rows:
                    if asset.host_id is None:
                        _attach(session, asset, host, user=user)
            elif decision == "DEACTIVATE":
                asset = rows[0]
                session.execute(
                    update(db_schema.IPAsset)
                    .where(db_schema.IPAsset.id == asset.id)
                    .values(archived=1, updated_at=func.current_timestamp())
                )
                _audit(
                    session,
                    user=user,
                    target_type="IP_ASSET",
                    target_id=int(asset.id),
                    label=str(asset.ip_address),
                    changes="Archived from reconciliation workflow.",
                )
            elif decision == "WRONG_PAIR" and len(rows) < 2:
                raise ReconciliationError(
                    422, "WRONG_PAIR requires a proposed OS/BMC pair."
                )

            os_address = next(
                (str(row.ip_address) for row in rows if row.type == "OS"), None
            )
            bmc_address = next(
                (str(row.ip_address) for row in rows if row.type == "BMC"), None
            )
            decision_row = db_schema.HostCompletionDecision(
                case_type=finding.kind,
                host_id=int(finding.host_id) if finding.host_id is not None else None,
                mode="SUGGEST"
                if finding.kind in {"CREATE_HOST", "COMPLETE_HOST"}
                else "ASK",
                os_address=os_address,
                bmc_address=bmc_address,
                candidate_ip=finding.candidate_ips[0]
                if finding.candidate_ips
                else None,
                corrected_ip=(
                    _normalize_counterpart_ip(counterpart_ip)
                    if decision == "CORRECT"
                    else None
                ),
                decision=decision,
                target_host_id=int(host.id) if host is not None else target_host_id,
                host_name=str(host.name)
                if host is not None
                else finding.proposed_host_name,
                proposal_id=proposal_id,
                inventory_fingerprint=inventory_fingerprint,
                idempotency_key=key,
                decided_by=user.id,
            )
            session.add(decision_row)
            session.flush()
            _audit(
                session,
                user=user,
                target_type="HOST_RECONCILIATION",
                target_id=int(decision_row.id),
                label=proposal_id,
                changes=f"Operator decision: {decision}.",
            )
            if created_host and host is not None:
                _audit(
                    session,
                    user=user,
                    target_type="HOST",
                    target_id=int(host.id),
                    label=str(host.name),
                    changes="Created by accepted reconciliation proposal.",
                )
            result_payload = {
                "id": int(decision_row.id),
                "decision": decision,
                "host_id": int(host.id) if host is not None else target_host_id,
                "proposal_id": proposal_id,
                "idempotent_replay": False,
            }
        return result_payload
    except ReconciliationError:
        session.rollback()
        raise
    finally:
        session.close()
