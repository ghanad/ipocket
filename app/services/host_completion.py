from __future__ import annotations

import ipaddress
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app import repository
from app.models import IPAssetType

from .host_completion_rules import CompletionRule, Transformation, infer_rules

MissingType = Literal["OS", "BMC", "any"]
CaseType = Literal[
    "UNLINKED_OS_PAIR",
    "UNLINKED_BMC_PAIR",
    "UNLINKED_OS",
    "UNLINKED_BMC",
    "HOST_MISSING_BMC",
    "HOST_MISSING_OS",
]


@dataclass(frozen=True)
class HostCompletionError(Exception):
    status_code: int
    detail: str


def get_min_support() -> int:
    try:
        return max(1, int(os.getenv("IPOCKET_HOST_COMPLETION_MIN_SUPPORT", "3")))
    except ValueError:
        return 3


def get_host_name_template() -> str:
    """Return the configurable name template used for BMC-backed Hosts."""

    return os.getenv("HOST_NAME_TEMPLATE", "server_{bmc}").strip() or "server_{bmc}"


def _template_bmc_address(name: str, template: str) -> str | None:
    """Extract an IPv4 BMC address only when a Host name exactly matches template."""

    if template.count("{bmc}") != 1:
        return None
    prefix, suffix = template.split("{bmc}")
    match = re.fullmatch(
        re.escape(prefix) + r"(?P<bmc>\d{1,3}(?:\.\d{1,3}){3})" + re.escape(suffix),
        name,
    )
    if not match:
        return None
    try:
        address = ipaddress.ip_address(match.group("bmc"))
    except ValueError:
        return None
    return str(address) if address.version == 4 else None


def _ip_sort_key(address: str) -> tuple[int, int, str]:
    try:
        parsed = ipaddress.ip_address(address)
        return (parsed.version, int(parsed), address)
    except ValueError:
        return (99, 0, address)


def _source_16(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(address)
        if parsed.version == 4:
            return str(ipaddress.ip_network(f"{parsed}/16", strict=False))
    except ValueError:
        pass
    return ""


def _address_pattern_key(source: str, target: str) -> tuple[str, str, bool] | None:
    try:
        source_address = ipaddress.ip_address(source)
        target_address = ipaddress.ip_address(target)
    except ValueError:
        return None
    if source_address.version != target_address.version or source_address.version != 4:
        return None
    source_network = ipaddress.ip_network(f"{source_address}/16", strict=False)
    target_network = ipaddress.ip_network(f"{target_address}/16", strict=False)
    host_mask = (1 << 16) - 1
    return (
        str(source_network),
        str(target_network),
        int(source_address) & host_mask == int(target_address) & host_mask,
    )


def get_analytics(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, object]:
    """Return active-inventory completion counters; no inventory is mutated."""

    source = repository.get_host_completion_analytics_source(connection_or_session)
    host_ids = {int(host_id) for host_id in source["host_ids"]}
    by_host: dict[int, dict[str, list[str]]] = defaultdict(
        lambda: {"OS": [], "BMC": []}
    )
    counts = {"BMC": 0, "OS": 0, "VM": 0, "unknown": 0}
    unlinked_os = unlinked_bmc = untyped_active = 0
    active_assets = source["assets"]
    assert isinstance(active_assets, list)
    for asset in active_assets:
        assert isinstance(asset, dict)
        asset_type = asset.get("type")
        if asset_type in {"BMC", "OS", "VM"}:
            counts[str(asset_type)] += 1
        else:
            counts["unknown"] += 1
        if asset_type is None:
            untyped_active += 1
        host_id = asset.get("host_id")
        if asset_type == "OS":
            if host_id is None:
                unlinked_os += 1
            elif int(host_id) in host_ids:
                by_host[int(host_id)]["OS"].append(str(asset["ip_address"]))
        elif asset_type == "BMC":
            if host_id is None:
                unlinked_bmc += 1
            elif int(host_id) in host_ids:
                by_host[int(host_id)]["BMC"].append(str(asset["ip_address"]))

    complete_hosts = hosts_missing_bmc = hosts_missing_os = blank_hosts = 0
    confirmed_pairs = 0
    patterns: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for host_id in host_ids:
        grouped = by_host[host_id]
        if grouped["OS"] and grouped["BMC"]:
            complete_hosts += 1
            for os_address in grouped["OS"]:
                for bmc_address in grouped["BMC"]:
                    confirmed_pairs += 1
                    key = _address_pattern_key(os_address, bmc_address)
                    if key:
                        patterns[(key[0], key[1])][0 if key[2] else 1] += 1
        elif grouped["OS"]:
            hosts_missing_bmc += 1
        elif grouped["BMC"]:
            hosts_missing_os += 1
        else:
            blank_hosts += 1
    total_active = len(active_assets)
    resolved = sum(
        1
        for asset in active_assets
        if asset.get("type") is not None
        and (asset.get("type") not in {"OS", "BMC"} or asset.get("host_id") is not None)
    )
    rendered_patterns = [
        {
            "source_prefix": source_prefix,
            "target_prefix": target_prefix,
            "support": values[0],
            "contradictions": values[1],
            "coverage_percent": round(values[0] * 100 / confirmed_pairs, 2)
            if confirmed_pairs
            else 0.0,
        }
        for (source_prefix, target_prefix), values in patterns.items()
        if values[0]
    ]
    rendered_patterns.sort(
        key=lambda row: (-int(row["support"]), str(row["source_prefix"]))
    )
    return {
        "total_hosts": len(host_ids),
        "complete_hosts": complete_hosts,
        "incomplete_hosts": len(host_ids) - complete_hosts,
        "breakdown": {
            "os_only": hosts_missing_bmc,
            "bmc_only": hosts_missing_os,
            "unlinked": blank_hosts,
        },
        "confirmed_pairs": confirmed_pairs,
        "patterns": rendered_patterns,
        "ip_type_counts": counts,
        "untyped_active": untyped_active,
        "unlinked_os": unlinked_os,
        "unlinked_bmc": unlinked_bmc,
        "hosts_missing_bmc": hosts_missing_bmc,
        "hosts_missing_os": hosts_missing_os,
        "inventory_health_percent": round(resolved * 100 / total_active, 2)
        if total_active
        else 100.0,
    }


def _page(records: list[dict[str, object]], limit: int) -> dict[str, object]:
    items = records[:limit]
    return {
        "items": items,
        "next_cursor": int(items[-1]["host_id"])
        if len(records) > limit and items
        else None,
    }


def list_incomplete_hosts(
    connection_or_session,
    *,
    missing: MissingType = "any",
    limit: int = 100,
    cursor: int | None = None,
) -> dict[str, object]:
    missing_type = None if missing == "any" else IPAssetType(missing)
    records = repository.list_host_completion_records(
        connection_or_session,
        kind="incomplete",
        missing_type=missing_type,
        after_host_id=cursor,
        limit=limit + 1,
    )
    for record in records:
        record["missing"] = "BMC" if record["os_assets"] else "OS"
    return _page(records, limit)


def list_confirmed_examples(
    connection_or_session, *, limit: int = 100, cursor: int | None = None
) -> dict[str, object]:
    return _page(
        repository.list_host_completion_records(
            connection_or_session,
            kind="complete",
            after_host_id=cursor,
            limit=limit + 1,
        ),
        limit,
    )


def _rejected_rule_pairs(decisions: list[dict[str, object]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in decisions:
        if item["decision"] != "REJECT":
            continue
        os_address = item.get("os_address")
        bmc_address = item.get("bmc_address")
        candidate = item.get("candidate_ip") or bmc_address
        if candidate is None:
            continue
        candidate = str(candidate)
        if os_address:
            pairs.append((str(os_address), candidate))
        elif bmc_address:
            pairs.append((candidate, str(bmc_address)))
    return pairs


def _engine_state(connection_or_session) -> dict[str, object]:
    source = repository.get_host_completion_engine_source(connection_or_session)
    assets = source["assets"]
    decisions = source["decisions"]
    assert isinstance(assets, list) and isinstance(decisions, list)
    active_assets = {
        str(asset["ip_address"]): asset for asset in assets if isinstance(asset, dict)
    }
    by_host: dict[int, dict[str, list[str]]] = defaultdict(
        lambda: {"OS": [], "BMC": []}
    )
    for address, asset in active_assets.items():
        if asset.get("host_id") is not None and asset.get("type") in {"OS", "BMC"}:
            by_host[int(asset["host_id"])][str(asset["type"])].append(address)
    pairs = [
        (os_address, bmc_address)
        for values in by_host.values()
        for os_address in values["OS"]
        for bmc_address in values["BMC"]
    ]
    return {
        "source": source,
        "active_assets": active_assets,
        "by_host": by_host,
        "rules": infer_rules(
            pairs,
            rejected_candidates=_rejected_rule_pairs(decisions),
            min_support=get_min_support(),
        ),
    }


def _reverse(rule: CompletionRule) -> Transformation:
    source = rule.transformation
    if source.kind == "prefix":
        assert source.source_prefix and source.target_prefix and source.prefix_length
        return Transformation(
            kind="prefix",
            source_16=str(ipaddress.ip_network(source.target_prefix)),
            source_prefix=source.target_prefix,
            target_prefix=source.source_prefix,
            prefix_length=source.prefix_length,
        )
    assert (
        source.octet_index is not None
        and source.source_octet is not None
        and source.target_octet is not None
    )
    # The source /16 guard must be based on the transformed address.
    sample = list(ipaddress.ip_network(source.source_16).network_address.packed)
    sample[source.octet_index] = source.target_octet
    return Transformation(
        kind="octet",
        source_16=str(
            ipaddress.ip_network(
                f"{ipaddress.ip_address(bytes(sample))}/16", strict=False
            )
        ),
        octet_index=source.octet_index,
        source_octet=source.target_octet,
        target_octet=source.source_octet,
    )


def _candidate_for(
    known_address: str, rules: list[CompletionRule], *, reverse: bool = False
):
    for rule in rules:
        candidate = (_reverse(rule) if reverse else rule.transformation).apply(
            known_address
        )
        if candidate:
            yield rule, candidate


def _was_rejected(
    decisions: list[dict[str, object]],
    *,
    host_id: int | None,
    os_address: str | None,
    bmc_address: str | None,
    candidate_ip: str | None,
) -> bool:
    for item in decisions:
        if item.get("decision") != "REJECT":
            continue
        if (
            host_id is not None
            and item.get("host_id") == host_id
            and item.get("candidate_ip") == candidate_ip
        ):
            return True
        if (
            os_address
            and item.get("os_address") == os_address
            and item.get("candidate_ip") == candidate_ip
        ):
            return True
        if (
            os_address
            and bmc_address
            and item.get("os_address") == os_address
            and item.get("bmc_address") == bmc_address
        ):
            return True
    return False


def _safe_candidate(
    *,
    candidate: str,
    expected_type: str,
    host_id: int | None,
    os_address: str | None,
    bmc_address: str | None,
    active_assets: dict[str, dict[str, object]],
    decisions: list[dict[str, object]],
) -> str | None:
    if _was_rejected(
        decisions,
        host_id=host_id,
        os_address=os_address,
        bmc_address=bmc_address,
        candidate_ip=candidate,
    ):
        return "Candidate was previously rejected for this host or asset."
    existing = active_assets.get(candidate)
    if existing is not None:
        if existing.get("host_id") not in {None, host_id}:
            return "Candidate is already linked to another host."
        if existing.get("type") != expected_type:
            return f"Candidate exists as a {existing.get('type') or 'untyped'} asset."
    return None


def _asset_view(address: str, asset: dict[str, object] | None) -> dict[str, object]:
    return (
        {"address": address, "hostname": None}
        if asset and asset.get("type") == "OS"
        else {"address": address}
    )


def _suggestion(
    *,
    case_type: CaseType,
    host_id: int | None,
    known_address: str,
    known_is_os: bool,
    active_assets: dict[str, dict[str, object]],
    rules: list[CompletionRule],
    decisions: list[dict[str, object]],
) -> dict[str, object]:
    expected = "BMC" if known_is_os else "OS"
    os_address = known_address if known_is_os else None
    bmc_address = known_address if not known_is_os else None
    first_failure: str | None = None
    for rule, candidate in _candidate_for(
        known_address, rules, reverse=not known_is_os
    ):
        failure = _safe_candidate(
            candidate=candidate,
            expected_type=expected,
            host_id=host_id,
            os_address=os_address,
            bmc_address=bmc_address,
            active_assets=active_assets,
            decisions=decisions,
        )
        if failure:
            first_failure = first_failure or failure
            continue
        evidence = list(rule.evidence)
        if active_assets.get(candidate) is not None:
            evidence.append(f"Existing unlinked {expected} asset will be linked.")
        return {
            "mode": "SUGGEST",
            "candidate_ip": candidate,
            "confidence": rule.confidence,
            "evidence": evidence,
            "reason_text": f"{rule.support} confirmed hosts use mapping {rule.transformation.description}",
        }
    return {
        "mode": "ASK",
        "candidate_ip": None,
        "confidence": None,
        "evidence": [],
        "reason_text": first_failure
        or f"No active mapping rule covers this {expected} candidate.",
    }


def _review_item(
    *,
    case_type: CaseType,
    host_id: int | None,
    os_address: str | None,
    bmc_address: str | None,
    would_create_host: bool,
    suggestion: dict[str, object],
    host_options: list[dict[str, object]],
) -> dict[str, object]:
    item: dict[str, object] = {
        "case_type": case_type,
        "mode": suggestion["mode"],
        "host_id": host_id,
        "os_asset": _asset_view(str(os_address), None) if os_address else None,
        "would_create_host": would_create_host,
        "candidate_ip": suggestion["candidate_ip"],
        "confidence": suggestion["confidence"],
        "evidence": suggestion["evidence"],
        "reason_text": suggestion["reason_text"],
        "host_name_template": get_host_name_template(),
        "host_options": host_options,
    }
    if bmc_address:
        item["bmc_asset"] = _asset_view(str(bmc_address), None)
    return item


def _host_options(
    hosts: list[object], by_host: dict[int, dict[str, list[str]]]
) -> list[dict[str, object]]:
    """Rank Host-name autocomplete choices without exposing a separate lookup API."""

    options: list[dict[str, object]] = []
    for raw_host in hosts:
        assert isinstance(raw_host, dict)
        host_id = int(raw_host["id"])
        sides = by_host.get(host_id, {"OS": [], "BMC": []})
        options.append(
            {
                "id": host_id,
                "name": str(raw_host["name"]),
                "has_os": bool(sides["OS"]),
                "has_bmc": bool(sides["BMC"]),
            }
        )
    recent_host_ids = {
        int(host["id"]) for host in hosts[-20:] if isinstance(host, dict)
    }
    # A Host missing either complement is the most useful attachment target,
    # followed by recently created Hosts, then a stable name ordering.
    options.sort(
        key=lambda option: (
            0 if not (bool(option["has_os"]) and bool(option["has_bmc"])) else 1,
            0 if int(option["id"]) in recent_host_ids else 1,
            -int(option["id"]) if int(option["id"]) in recent_host_ids else 0,
            str(option["name"]).lower(),
        )
    )
    return options[:20]


def build_review_queue(connection_or_session) -> dict[str, object]:
    state = _engine_state(connection_or_session)
    source = state["source"]
    active_assets = state["active_assets"]
    by_host = state["by_host"]
    rules = state["rules"]
    assert (
        isinstance(source, dict)
        and isinstance(active_assets, dict)
        and isinstance(by_host, dict)
        and isinstance(rules, list)
    )
    decisions = source["decisions"]
    hosts = source["hosts"]
    assert isinstance(decisions, list) and isinstance(hosts, list)
    host_options = _host_options(hosts, by_host)
    unlinked_os = {
        address
        for address, asset in active_assets.items()
        if asset.get("type") == "OS" and asset.get("host_id") is None
    }
    unlinked_bmc = {
        address
        for address, asset in active_assets.items()
        if asset.get("type") == "BMC" and asset.get("host_id") is None
    }
    queued: list[tuple[int, str, str, dict[str, object]]] = []

    # Names that encode a BMC provide deterministic, high-confidence suggestions.
    template = get_host_name_template()
    name_claims: list[tuple[int, str, str]] = []
    for host in hosts:
        assert isinstance(host, dict)
        host_id = int(host["id"])
        bmc_address = _template_bmc_address(str(host["name"]), template)
        if (
            bmc_address
            and not by_host.get(host_id, {"BMC": []})["BMC"]
            and bmc_address in unlinked_bmc
        ):
            name_claims.append((host_id, str(host["name"]), bmc_address))
    named_host_ids = {host_id for host_id, _, _ in name_claims}
    for host_id, host_name, bmc_address in sorted(
        name_claims, key=lambda row: _ip_sort_key(row[2])
    ):
        queued.append(
            (
                1,
                _source_16(bmc_address),
                bmc_address,
                _review_item(
                    case_type="HOST_MISSING_BMC",
                    host_id=host_id,
                    os_address=None,
                    bmc_address=None,
                    would_create_host=False,
                    suggestion={
                        "mode": "SUGGEST",
                        "candidate_ip": bmc_address,
                        "confidence": 0.95,
                        "evidence": ["host name encodes the BMC address"],
                        "reason_text": f"Host '{host_name}' matches the configured BMC name template.",
                    },
                    host_options=host_options,
                ),
            )
        )

    # Pass one records all possible claims before consuming so the strongest rule wins.
    claims: list[tuple[float, str, str, CompletionRule]] = []
    for os_address in sorted(unlinked_os, key=_ip_sort_key):
        for rule, candidate in _candidate_for(os_address, rules):
            if candidate in unlinked_bmc and not _was_rejected(
                decisions,
                host_id=None,
                os_address=os_address,
                bmc_address=candidate,
                candidate_ip=candidate,
            ):
                claims.append((rule.confidence, os_address, candidate, rule))
    consumed_os: set[str] = set()
    consumed_bmc: set[str] = set()
    for confidence, os_address, bmc_address, rule in sorted(
        claims,
        key=lambda row: (
            -row[0],
            _ip_sort_key(row[1]),
            _ip_sort_key(row[2]),
            row[3].transformation.description,
        ),
    ):
        if os_address in consumed_os or bmc_address in consumed_bmc:
            continue
        consumed_os.add(os_address)
        consumed_bmc.add(bmc_address)
        suggestion = {
            "mode": "SUGGEST",
            "candidate_ip": None,
            "confidence": min(confidence + 0.05, 1.0),
            "evidence": [
                *rule.evidence,
                f"both assets exist unlinked and match rule {rule.transformation.description}",
            ],
            "reason_text": f"{rule.support} confirmed hosts use mapping {rule.transformation.description}",
        }
        queued.append(
            (
                0,
                _source_16(os_address),
                os_address,
                _review_item(
                    case_type="UNLINKED_OS_PAIR",
                    host_id=None,
                    os_address=os_address,
                    bmc_address=bmc_address,
                    would_create_host=True,
                    suggestion=suggestion,
                    host_options=host_options,
                ),
            )
        )

    # Pass two is reverse only for still-unconsumed BMC addresses.
    reverse_claims: list[tuple[float, str, str, CompletionRule]] = []
    for bmc_address in sorted(unlinked_bmc - consumed_bmc, key=_ip_sort_key):
        for rule, candidate in _candidate_for(bmc_address, rules, reverse=True):
            if candidate in unlinked_os - consumed_os and not _was_rejected(
                decisions,
                host_id=None,
                os_address=candidate,
                bmc_address=bmc_address,
                candidate_ip=candidate,
            ):
                reverse_claims.append((rule.confidence, candidate, bmc_address, rule))
    for confidence, os_address, bmc_address, rule in sorted(
        reverse_claims,
        key=lambda row: (-row[0], _ip_sort_key(row[1]), _ip_sort_key(row[2])),
    ):
        if os_address in consumed_os or bmc_address in consumed_bmc:
            continue
        consumed_os.add(os_address)
        consumed_bmc.add(bmc_address)
        suggestion = {
            "mode": "SUGGEST",
            "candidate_ip": None,
            "confidence": min(confidence + 0.05, 1.0),
            "evidence": [
                *rule.evidence,
                f"both assets exist unlinked and match rule {rule.transformation.description}",
            ],
            "reason_text": f"{rule.support} confirmed hosts use mapping {rule.transformation.description}",
        }
        queued.append(
            (
                0,
                _source_16(bmc_address),
                bmc_address,
                _review_item(
                    case_type="UNLINKED_BMC_PAIR",
                    host_id=None,
                    os_address=os_address,
                    bmc_address=bmc_address,
                    would_create_host=True,
                    suggestion=suggestion,
                    host_options=host_options,
                ),
            )
        )

    flags = {
        (int(item["host_id"]), str(item["decision"]))
        for item in decisions
        if item.get("host_id") is not None and item["decision"] in {"NO_BMC", "NO_OS"}
    }
    host_items: list[tuple[dict[str, object], CaseType, str, bool]] = []
    for host in hosts:
        assert isinstance(host, dict)
        host_id = int(host["id"])
        grouped = by_host.get(host_id, {"OS": [], "BMC": []})
        if (
            grouped["OS"]
            and not grouped["BMC"]
            and (host_id, "NO_BMC") not in flags
            and host_id not in named_host_ids
        ):
            host_items.append(
                (host, "HOST_MISSING_BMC", min(grouped["OS"], key=_ip_sort_key), True)
            )
        if grouped["BMC"] and not grouped["OS"] and (host_id, "NO_OS") not in flags:
            host_items.append(
                (host, "HOST_MISSING_OS", min(grouped["BMC"], key=_ip_sort_key), False)
            )
    for host, case_type, known, known_is_os in host_items:
        suggestion = _suggestion(
            case_type=case_type,
            host_id=int(host["id"]),
            known_address=known,
            known_is_os=known_is_os,
            active_assets=active_assets,
            rules=rules,
            decisions=decisions,
        )
        queued.append(
            (
                1 if suggestion["mode"] == "SUGGEST" else 3,
                _source_16(known),
                known,
                _review_item(
                    case_type=case_type,
                    host_id=int(host["id"]),
                    os_address=known if known_is_os else None,
                    bmc_address=known if not known_is_os else None,
                    would_create_host=False,
                    suggestion=suggestion,
                    host_options=host_options,
                ),
            )
        )
    for os_address in sorted(unlinked_os - consumed_os, key=_ip_sort_key):
        suggestion = _suggestion(
            case_type="UNLINKED_OS",
            host_id=None,
            known_address=os_address,
            known_is_os=True,
            active_assets=active_assets,
            rules=rules,
            decisions=decisions,
        )
        queued.append(
            (
                2,
                _source_16(os_address),
                os_address,
                _review_item(
                    case_type="UNLINKED_OS",
                    host_id=None,
                    os_address=os_address,
                    bmc_address=None,
                    would_create_host=True,
                    suggestion=suggestion,
                    host_options=host_options,
                ),
            )
        )
    for bmc_address in sorted(unlinked_bmc - consumed_bmc, key=_ip_sort_key):
        suggestion = _suggestion(
            case_type="UNLINKED_BMC",
            host_id=None,
            known_address=bmc_address,
            known_is_os=False,
            active_assets=active_assets,
            rules=rules,
            decisions=decisions,
        )
        queued.append(
            (
                2,
                _source_16(bmc_address),
                bmc_address,
                _review_item(
                    case_type="UNLINKED_BMC",
                    host_id=None,
                    os_address=None,
                    bmc_address=bmc_address,
                    would_create_host=True,
                    suggestion=suggestion,
                    host_options=host_options,
                ),
            )
        )
    prefix_counts: dict[tuple[int, str], int] = defaultdict(int)
    for group, prefix, _, _ in queued:
        prefix_counts[(group, prefix)] += 1
    queued.sort(
        key=lambda row: (
            row[0],
            -prefix_counts[(row[0], row[1])],
            row[1],
            _ip_sort_key(row[2]),
        )
    )
    return {
        "item": queued[0][3] if queued else None,
        "remaining": max(len(queued) - 1, 0),
    }


def _normalize_ip(
    value: str | None, field: str, *, required: bool = False
) -> str | None:
    if not value:
        if required:
            raise HostCompletionError(422, f"{field} is required.")
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise HostCompletionError(422, f"{field} must be a valid IP address.") from exc


def _require_host_name(host_name: str | None) -> str:
    if not host_name or not host_name.strip():
        raise HostCompletionError(422, "host_name is required when creating a Host.")
    return host_name.strip()


def _create_host(connection_or_session, name: str, user) -> int:
    try:
        return repository.create_host(
            connection_or_session, name=name, current_user=user
        ).id
    except sqlite3.IntegrityError as exc:
        raise HostCompletionError(409, "Host name already exists.") from exc


def _resolve_or_create_host(connection_or_session, name: str, user) -> tuple[int, bool]:
    """Resolve a trimmed, case-insensitive Host name before creating one."""

    existing = repository.get_host_by_name(connection_or_session, name)
    if existing is not None:
        return existing.id, True
    return _create_host(connection_or_session, name, user), False


def _validate_bmc_attachment(
    connection_or_session, host_id: int, bmc_address: str | None
) -> None:
    """A Host has one active BMC identity; repeating it is safely idempotent."""

    if not bmc_address:
        return
    state = _engine_state(connection_or_session)
    by_host = state["by_host"]
    assert isinstance(by_host, dict)
    existing_bmcs = by_host.get(host_id, {"BMC": []})["BMC"]
    if existing_bmcs and bmc_address not in existing_bmcs:
        host = repository.get_host_by_id(connection_or_session, host_id)
        label = host.name if host else str(host_id)
        raise HostCompletionError(
            409,
            f"Host '{label}' already has active BMC IP {existing_bmcs[0]}; cannot attach different BMC IP {bmc_address}.",
        )


def _host_completion_message(
    connection_or_session,
    host_id: int,
    *,
    existing: bool,
    address: str | None,
    asset_type: str | None,
) -> str | None:
    if not existing:
        return None
    host = repository.get_host_by_id(connection_or_session, host_id)
    if host is None:
        return None
    state = _engine_state(connection_or_session)
    by_host = state["by_host"]
    assert isinstance(by_host, dict)
    sides = by_host.get(host_id, {"OS": [], "BMC": []})
    suffix = " Host is now complete." if sides["OS"] and sides["BMC"] else ""
    if address and asset_type:
        return (
            f"{asset_type} {address} attached to existing host '{host.name}'.{suffix}"
        )
    return f"Assets attached to existing host '{host.name}'.{suffix}"


def _link_asset(
    connection_or_session, *, address: str, asset_type: str, host_id: int, user
) -> None:
    existing = repository.get_ip_asset_by_ip(connection_or_session, address)
    if (
        existing is not None
        and not existing.archived
        and existing.host_id not in {None, host_id}
    ):
        raise HostCompletionError(409, "IP address is already linked to another host.")
    try:
        if existing is None or existing.archived:
            repository.create_ip_asset(
                connection_or_session,
                address,
                IPAssetType(asset_type),
                host_id=host_id,
                current_user=user,
            )
        else:
            repository.update_ip_asset(
                connection_or_session,
                address,
                asset_type=IPAssetType(asset_type),
                host_id=host_id,
                host_id_provided=True,
                current_user=user,
            )
    except sqlite3.IntegrityError as exc:
        raise HostCompletionError(409, "IP address already exists.") from exc


def _existing_active(connection_or_session, address: str, label: str):
    asset = repository.get_ip_asset_by_ip(connection_or_session, address)
    if asset is None or asset.archived:
        raise HostCompletionError(404, f"{label} asset not found or inactive.")
    return asset


def _same_decision(
    decisions,
    *,
    case_type,
    mode,
    host_id,
    os_address,
    bmc_address,
    candidate_ip,
    corrected_ip,
    decision,
    target_host_id,
    host_name,
):
    for item in decisions:
        values = {
            "case_type": case_type,
            "mode": mode,
            "host_id": host_id,
            "os_address": os_address,
            "bmc_address": bmc_address,
            "candidate_ip": candidate_ip,
            "corrected_ip": corrected_ip,
            "decision": decision,
            "host_name": host_name,
        }
        if all(item.get(key) == value for key, value in values.items()) and (
            target_host_id is None or item.get("target_host_id") == target_host_id
        ):
            return item
    return None


def record_decision(
    connection_or_session,
    *,
    case_type: str,
    mode: str,
    host_id: int | None,
    os_address: str | None,
    bmc_address: str | None,
    decision: str,
    candidate_ip: str | None,
    corrected_ip: str | None,
    target_host_id: int | None,
    host_name: str | None,
    user,
) -> dict[str, object]:
    if (
        host_id is not None
        and repository.get_host_by_id(connection_or_session, host_id) is None
    ):
        raise HostCompletionError(404, "Host not found.")
    if (
        target_host_id is not None
        and repository.get_host_by_id(connection_or_session, target_host_id) is None
    ):
        raise HostCompletionError(404, "Target Host not found.")
    os_address = _normalize_ip(os_address, "os_address")
    bmc_address = _normalize_ip(bmc_address, "bmc_address")
    candidate_ip = _normalize_ip(candidate_ip, "candidate_ip")
    corrected_ip = _normalize_ip(corrected_ip, "corrected_ip")
    state = _engine_state(connection_or_session)
    source = state["source"]
    assert isinstance(source, dict)
    duplicate = _same_decision(
        source["decisions"],
        case_type=case_type,
        mode=mode,
        host_id=host_id,
        os_address=os_address,
        bmc_address=bmc_address,
        candidate_ip=candidate_ip,
        corrected_ip=corrected_ip,
        decision=decision,
        target_host_id=target_host_id,
        host_name=host_name,
    )
    if duplicate:
        return {
            "id": int(duplicate["id"]),
            "decision": decision,
            "applied_ip": corrected_ip or candidate_ip,
            "host_id": duplicate.get("target_host_id") or host_id,
            "message": None,
        }

    creates_host = (
        decision in {"CREATE_HOST_ONLY"}
        or (
            decision in {"ACCEPT", "CORRECTED"}
            and case_type
            in {"UNLINKED_OS_PAIR", "UNLINKED_BMC_PAIR", "UNLINKED_OS", "UNLINKED_BMC"}
        )
        or (decision in {"NO_BMC", "NO_OS"} and host_id is None)
    )
    if creates_host:
        host_name = _require_host_name(host_name)
    resolved_host_id = host_id
    resolved_existing_host = False
    applied_ip: str | None = None
    chosen_ip = corrected_ip if decision == "CORRECTED" else candidate_ip

    if decision in {"ACCEPT", "CORRECTED"}:
        if case_type in {"UNLINKED_OS_PAIR", "UNLINKED_BMC_PAIR"}:
            if not os_address or not bmc_address:
                raise HostCompletionError(
                    422, "os_address and bmc_address are required for a pair."
                )
            resolved_host_id, resolved_existing_host = _resolve_or_create_host(
                connection_or_session, _require_host_name(host_name), user
            )
            if resolved_existing_host:
                _validate_bmc_attachment(
                    connection_or_session, resolved_host_id, chosen_ip or bmc_address
                )
            _link_asset(
                connection_or_session,
                address=os_address,
                asset_type="OS",
                host_id=resolved_host_id,
                user=user,
            )
            _link_asset(
                connection_or_session,
                address=chosen_ip or bmc_address,
                asset_type="BMC",
                host_id=resolved_host_id,
                user=user,
            )
            applied_ip = chosen_ip or bmc_address
        elif case_type in {"UNLINKED_OS", "UNLINKED_BMC"}:
            known = os_address if case_type == "UNLINKED_OS" else bmc_address
            if not known:
                raise HostCompletionError(422, "Known asset address is required.")
            if not chosen_ip:
                raise HostCompletionError(422, "candidate_ip is required.")
            resolved_host_id, resolved_existing_host = _resolve_or_create_host(
                connection_or_session, _require_host_name(host_name), user
            )
            if resolved_existing_host:
                _validate_bmc_attachment(
                    connection_or_session,
                    resolved_host_id,
                    chosen_ip if case_type == "UNLINKED_OS" else bmc_address,
                )
            _link_asset(
                connection_or_session,
                address=known,
                asset_type="OS" if case_type == "UNLINKED_OS" else "BMC",
                host_id=resolved_host_id,
                user=user,
            )
            _link_asset(
                connection_or_session,
                address=chosen_ip,
                asset_type="BMC" if case_type == "UNLINKED_OS" else "OS",
                host_id=resolved_host_id,
                user=user,
            )
            applied_ip = chosen_ip
        elif case_type in {"HOST_MISSING_BMC", "HOST_MISSING_OS"}:
            if resolved_host_id is None:
                raise HostCompletionError(
                    422, "host_id is required for a host-missing case."
                )
            if not chosen_ip:
                raise HostCompletionError(422, "candidate_ip is required.")
            _link_asset(
                connection_or_session,
                address=chosen_ip,
                asset_type="BMC" if case_type == "HOST_MISSING_BMC" else "OS",
                host_id=resolved_host_id,
                user=user,
            )
            applied_ip = chosen_ip
        else:
            raise HostCompletionError(422, "Unsupported case_type.")
    elif decision == "CREATE_HOST_ONLY":
        address = os_address or bmc_address
        if not address:
            raise HostCompletionError(422, "os_address or bmc_address is required.")
        asset = _existing_active(connection_or_session, address, "Known")
        if asset.asset_type not in {IPAssetType.OS, IPAssetType.BMC}:
            raise HostCompletionError(422, "Known asset must be typed OS or BMC.")
        resolved_host_id, resolved_existing_host = _resolve_or_create_host(
            connection_or_session, _require_host_name(host_name), user
        )
        _link_asset(
            connection_or_session,
            address=address,
            asset_type=asset.asset_type.value,
            host_id=resolved_host_id,
            user=user,
        )
    elif decision in {"NO_BMC", "NO_OS"}:
        if host_id is None:
            address = os_address or bmc_address
            if not address:
                raise HostCompletionError(422, "Known asset address is required.")
            asset = _existing_active(connection_or_session, address, "Known")
            if asset.asset_type not in {IPAssetType.OS, IPAssetType.BMC}:
                raise HostCompletionError(422, "Known asset must be typed OS or BMC.")
            resolved_host_id, resolved_existing_host = _resolve_or_create_host(
                connection_or_session, _require_host_name(host_name), user
            )
            _link_asset(
                connection_or_session,
                address=address,
                asset_type=asset.asset_type.value,
                host_id=resolved_host_id,
                user=user,
            )
    elif decision == "ATTACH_EXISTING":
        if target_host_id is None:
            raise HostCompletionError(422, "target_host_id is required.")
        addresses = [(os_address, "OS"), (bmc_address, "BMC")]
        if not any(address for address, _ in addresses):
            raise HostCompletionError(422, "os_address or bmc_address is required.")
        _validate_bmc_attachment(connection_or_session, target_host_id, bmc_address)
        for address, asset_type in addresses:
            if address:
                _existing_active(connection_or_session, address, asset_type)
                _link_asset(
                    connection_or_session,
                    address=address,
                    asset_type=asset_type,
                    host_id=target_host_id,
                    user=user,
                )
        resolved_host_id = target_host_id
    elif decision == "DEACTIVATE":
        address = os_address or bmc_address
        if not address:
            raise HostCompletionError(422, "os_address or bmc_address is required.")
        _existing_active(connection_or_session, address, "Selected")
        repository.archive_ip_asset(connection_or_session, address, current_user=user)
        applied_ip = address
    elif decision not in {"REJECT", "UNSURE"}:
        raise HostCompletionError(422, "Unsupported decision.")

    decision_id = repository.create_host_completion_decision(
        connection_or_session,
        case_type=case_type,
        host_id=host_id,
        mode=mode,
        os_address=os_address,
        bmc_address=bmc_address,
        candidate_ip=candidate_ip,
        corrected_ip=corrected_ip,
        decision=decision,
        target_host_id=resolved_host_id if creates_host else target_host_id,
        host_name=host_name,
        decided_by=user.id,
    )
    return {
        "id": decision_id,
        "decision": decision,
        "applied_ip": applied_ip,
        "host_id": resolved_host_id,
        "message": _host_completion_message(
            connection_or_session,
            resolved_host_id,
            existing=resolved_existing_host or decision == "ATTACH_EXISTING",
            address=os_address or bmc_address or chosen_ip,
            asset_type="OS"
            if os_address
            else "BMC"
            if bmc_address or chosen_ip
            else None,
        )
        if resolved_host_id is not None
        else None,
    }
