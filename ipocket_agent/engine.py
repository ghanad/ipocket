"""Pure deterministic reconciliation engine for an ipocket inventory snapshot."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from collections import defaultdict
from typing import Iterable

from .models import (
    AgentDecision,
    Asset,
    Finding,
    Host,
    Inventory,
    ReconciliationResult,
    Rule,
    RuleStrength,
    Transformation,
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def _ip_key(value: str) -> tuple[int, str]:
    try:
        return (int(ipaddress.IPv4Address(value)), value)
    except ipaddress.AddressValueError:
        return (2**32, value)


def _ipv4_pair(os_ip: str, bmc_ip: str):
    try:
        return ipaddress.IPv4Address(os_ip), ipaddress.IPv4Address(bmc_ip)
    except ipaddress.AddressValueError:
        return None


def _pair_transformations(os_ip: str, bmc_ip: str) -> set[Transformation]:
    pair = _ipv4_pair(os_ip, bmc_ip)
    if pair is None:
        return set()
    source, target = pair
    transformations: set[Transformation] = set()
    for length, kind in ((16, "PREFIX_16"), (24, "PREFIX_24")):
        host_mask = (1 << (32 - length)) - 1
        if int(source) & host_mask == int(target) & host_mask:
            transformations.add(
                Transformation(
                    kind=kind,
                    source=str(ipaddress.ip_network(f"{source}/{length}", strict=False)),
                    target=str(ipaddress.ip_network(f"{target}/{length}", strict=False)),
                )
            )
    source_octets, target_octets = source.packed, target.packed
    changed = [i for i in range(4) if source_octets[i] != target_octets[i]]
    if len(changed) == 1:
        index = changed[0]
        transformations.add(
            Transformation(
                kind="OCTET",
                source=str(source_octets[index]),
                target=str(target_octets[index]),
                octet_index=index,
                source_scope=str(ipaddress.ip_network(f"{source}/16", strict=False)),
                target_scope=str(ipaddress.ip_network(f"{target}/16", strict=False)),
            )
        )
    return transformations


def _apply(transformation: Transformation, address: str, *, reverse: bool = False) -> str | None:
    try:
        parsed = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError:
        return None
    source, target = transformation.source, transformation.target
    if reverse:
        source, target = target, source
    if transformation.kind in {"PREFIX_16", "PREFIX_24"}:
        source_network = ipaddress.ip_network(source)
        if parsed not in source_network:
            return None
        target_network = ipaddress.ip_network(target)
        host_mask = (1 << (32 - source_network.prefixlen)) - 1
        return str(ipaddress.IPv4Address(int(target_network.network_address) | (int(parsed) & host_mask)))
    assert transformation.octet_index is not None
    source_octet, target_octet = int(source), int(target)
    scope = transformation.target_scope if reverse else transformation.source_scope
    if scope is not None and parsed not in ipaddress.ip_network(scope):
        return None
    octets = list(parsed.packed)
    if octets[transformation.octet_index] != source_octet:
        return None
    octets[transformation.octet_index] = target_octet
    return str(ipaddress.IPv4Address(bytes(octets)))


def _rule_strength(support: int, contradictions: int, min_support: int) -> tuple[bool, RuleStrength]:
    if support < min_support or contradictions >= support:
        return False, "INACTIVE"
    if contradictions == 0:
        return True, "STRONG"
    return True, "MODERATE"


def _confirmed_pairs(inventory: Inventory) -> list[tuple[str, str]]:
    active_assets = [
        asset
        for asset in inventory.assets
        if not asset.archived and asset.asset_type in {"OS", "BMC"} and asset.host_id
    ]
    by_host: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"OS": [], "BMC": []})
    for asset in active_assets:
        by_host[asset.host_id or ""][asset.asset_type].append(asset.ip_address)
    return sorted(
        [
            (os_ip, bmc_ip)
            for sides in by_host.values()
            for os_ip in sides["OS"]
            for bmc_ip in sides["BMC"]
        ],
        key=lambda pair: (_ip_key(pair[0]), _ip_key(pair[1])),
    )


def _wrong_pairs(decisions: Iterable[AgentDecision]) -> set[tuple[str, str]]:
    return {
        (decision.os_ip, decision.bmc_ip)
        for decision in decisions
        if decision.kind == "WRONG_PAIR" and decision.os_ip is not None and decision.bmc_ip is not None
    }


def discover_rules(inventory: Inventory, *, min_support: int = 3) -> tuple[Rule, ...]:
    """Discover inspectable rules from active, confirmed OS/BMC host pairs only."""

    if min_support < 1:
        raise ValueError("min_support must be at least one")
    pairs = _confirmed_pairs(inventory)
    candidates = {rule for pair in pairs for rule in _pair_transformations(*pair)}
    wrong_pairs = _wrong_pairs(inventory.decisions)
    rules: list[Rule] = []
    for transformation in candidates:
        matching = tuple(pair for pair in pairs if _apply(transformation, pair[0]) == pair[1])
        support = len(matching)
        # A confirmed pair is a contradiction only if the transformation applies
        # to its OS address but predicts a different BMC.
        contradictions = sum(
            1
            for os_ip, bmc_ip in pairs
            if _apply(transformation, os_ip) is not None and _apply(transformation, os_ip) != bmc_ip
        )
        contradictions += sum(
            1
            for os_ip, bmc_ip in wrong_pairs
            if _apply(transformation, os_ip) == bmc_ip
        )
        active, strength = _rule_strength(support, contradictions, min_support)
        rule_id = _digest((
            transformation.kind,
            transformation.source,
            transformation.target,
            transformation.octet_index,
            transformation.source_scope,
            transformation.target_scope,
        ))
        rules.append(
            Rule(
                id=rule_id,
                transformation=transformation,
                support=support,
                contradictions=contradictions,
                examples=matching,
                active=active,
                strength=strength,
            )
        )
    return tuple(sorted(rules, key=lambda rule: (not rule.active, -rule.support, rule.contradictions, rule.id)))


def _asset_snapshot(asset: Asset) -> tuple[str, ...]:
    return ("asset", asset.id, asset.ip_address, asset.asset_type, asset.host_id or "", str(asset.archived))


def _host_snapshot(host: Host) -> tuple[str, ...]:
    return ("host", host.id, host.name)


def _finding(
    inventory: Inventory,
    *,
    kind: str,
    assets: Iterable[Asset] = (),
    host: Host | None = None,
    candidate_ips: Iterable[str] = (),
    proposed_host_name: str | None = None,
    rules: Iterable[Rule] = (),
    reasons: Iterable[str] = (),
) -> Finding:
    asset_list = tuple(sorted(assets, key=lambda asset: asset.id))
    rule_list = tuple(sorted(rules, key=lambda rule: rule.id))
    assumptions = tuple(_asset_snapshot(asset) for asset in asset_list) + (() if host is None else (_host_snapshot(host),))
    fingerprint = _digest(assumptions)
    candidate_ips = tuple(sorted(set(candidate_ips), key=_ip_key))
    proposal_id = _digest((kind, tuple(asset.id for asset in asset_list), host.id if host else None, candidate_ips, tuple(rule.id for rule in rule_list), fingerprint))
    evidence = tuple(
        f"{rule.support} confirmed pair(s) use {rule.transformation.description}; {rule.contradictions} contradiction(s)."
        for rule in rule_list
    )
    strengths = {rule.strength for rule in rule_list}
    strength: RuleStrength | None = "STRONG" if strengths == {"STRONG"} else ("MODERATE" if rule_list else None)
    return Finding(
        kind=kind,  # type: ignore[arg-type]
        proposal_id=proposal_id,
        inventory_fingerprint=fingerprint,
        asset_ids=tuple(asset.id for asset in asset_list),
        host_id=host.id if host else None,
        candidate_ips=candidate_ips,
        proposed_host_name=proposed_host_name,
        rule_ids=tuple(rule.id for rule in rule_list),
        strength=strength,
        evidence=evidence,
        reasons=tuple(reasons),
        assumptions=assumptions,
    )


def proposal_is_current(finding: Finding, inventory: Inventory) -> bool:
    """Return whether the assets/host assumed by ``finding`` are unchanged."""

    assets = {asset.id: asset for asset in inventory.assets}
    hosts = {host.id: host for host in inventory.hosts}
    current: list[tuple[str, ...]] = []
    for snapshot in finding.assumptions:
        if snapshot[0] == "asset":
            asset = assets.get(snapshot[1])
            if asset is None:
                return False
            current.append(_asset_snapshot(asset))
        else:
            host = hosts.get(snapshot[1])
            if host is None:
                return False
            current.append(_host_snapshot(host))
    return _digest(tuple(current)) == finding.inventory_fingerprint


def _candidate_rules(address: str, rules: Iterable[Rule], *, reverse: bool = False) -> list[tuple[Rule, str]]:
    return [
        (rule, candidate)
        for rule in rules
        if rule.active and rule.strength == "STRONG"
        for candidate in [_apply(rule.transformation, address, reverse=reverse)]
        if candidate is not None
    ]


def reconcile(inventory: Inventory, *, min_support: int = 3, host_name_template: str = "server_{bmc}") -> ReconciliationResult:
    """Classify an inventory snapshot without changing it.

    Only active OS/BMC assets participate.  Rules are evidence, so only an
    unambiguous STRONG rule can yield a host proposal; unsafe candidates always
    become explicit conflicts instead of an attachment suggestion.
    """

    if host_name_template.count("{bmc}") != 1:
        raise ValueError("host_name_template must contain exactly one {bmc}")
    rules = discover_rules(inventory, min_support=min_support)
    assets_by_ip = {asset.ip_address: asset for asset in inventory.assets}
    hosts = {host.id: host for host in inventory.hosts}
    active = tuple(asset for asset in inventory.assets if not asset.archived and asset.asset_type in {"OS", "BMC"})
    by_host: dict[str, dict[str, list[Asset]]] = defaultdict(lambda: {"OS": [], "BMC": []})
    for asset in active:
        if asset.host_id:
            by_host[asset.host_id][asset.asset_type].append(asset)
    exceptions = {decision.asset_id for decision in inventory.decisions if decision.kind == "EXCEPTION" and decision.asset_id}
    deferred = {decision.asset_id for decision in inventory.decisions if decision.kind == "UNSURE" and decision.asset_id}
    wrong_pairs = _wrong_pairs(inventory.decisions)
    findings: list[Finding] = []
    proposed_ids: set[str] = set()
    conflict_ids: set[str] = set()

    def conflict(origin: Asset, candidate: Asset | None, candidates: Iterable[str], reason: str, rule_items: Iterable[Rule]) -> None:
        involved = (origin,) if candidate is None else (origin, candidate)
        findings.append(_finding(inventory, kind="CONFLICT", assets=involved, candidate_ips=candidates, rules=rule_items, reasons=(reason,)))
        conflict_ids.update(asset.id for asset in involved)

    # Incomplete hosts are handled before unlinked pairs so their intended host
    # is unambiguous and a candidate cannot be reported as CREATE_HOST as well.
    consumed_unlinked: set[str] = set()
    for host_id, sides in sorted(by_host.items()):
        host = hosts.get(host_id)
        if host is None:
            continue
        if bool(sides["OS"]) == bool(sides["BMC"]):
            continue
        known = sides["OS"] if sides["OS"] else sides["BMC"]
        expected_type = "BMC" if sides["OS"] else "OS"
        for source in known:
            candidate_rules = _candidate_rules(source.ip_address, rules, reverse=expected_type == "OS")
            valid: list[tuple[Rule, Asset]] = []
            for rule, address in candidate_rules:
                candidate = assets_by_ip.get(address)
                if candidate is None or candidate.archived:
                    continue
                if candidate.asset_type != expected_type:
                    conflict(source, candidate, (address,), f"Candidate exists with incompatible type {candidate.asset_type}.", (rule,))
                elif candidate.host_id not in {None, host.id}:
                    conflict(source, candidate, (address,), "Candidate is already attached to another Host.", (rule,))
                elif candidate.host_id is None and (source.ip_address, address) not in wrong_pairs and (address, source.ip_address) not in wrong_pairs:
                    valid.append((rule, candidate))
            distinct = {candidate.id for _, candidate in valid}
            if len(distinct) > 1:
                conflict(source, None, (candidate.ip_address for _, candidate in valid), "Multiple strong candidates are ambiguous.", (rule for rule, _ in valid))
            elif valid:
                rule, candidate = valid[0]
                findings.append(_finding(inventory, kind="COMPLETE_HOST", assets=(source, candidate), host=host, candidate_ips=(candidate.ip_address,), rules=(rule,), reasons=(f"Host is missing its {expected_type} relationship.",)))
                proposed_ids.update((source.id, candidate.id))
                consumed_unlinked.add(candidate.id)

    # A CREATE_HOST is generated from the OS direction only, so the same physical
    # pair cannot recur in the BMC direction.
    for os_asset in sorted((asset for asset in active if asset.asset_type == "OS" and asset.host_id is None), key=lambda asset: _ip_key(asset.ip_address)):
        if os_asset.id in consumed_unlinked or os_asset.id in exceptions:
            continue
        valid: list[tuple[Rule, Asset]] = []
        for rule, address in _candidate_rules(os_asset.ip_address, rules):
            candidate = assets_by_ip.get(address)
            if candidate is None or candidate.archived:
                continue
            if (os_asset.ip_address, address) in wrong_pairs:
                continue
            if candidate.asset_type != "BMC":
                conflict(os_asset, candidate, (address,), f"Candidate exists with incompatible type {candidate.asset_type}.", (rule,))
            elif candidate.host_id is not None:
                conflict(os_asset, candidate, (address,), "Candidate is already attached to another Host.", (rule,))
            else:
                valid.append((rule, candidate))
        distinct = {candidate.id for _, candidate in valid}
        if len(distinct) > 1:
            conflict(os_asset, None, (candidate.ip_address for _, candidate in valid), "Multiple strong candidates are ambiguous.", (rule for rule, _ in valid))
        elif valid:
            rule, bmc_asset = valid[0]
            if bmc_asset.id not in consumed_unlinked and bmc_asset.id not in exceptions:
                findings.append(_finding(inventory, kind="CREATE_HOST", assets=(os_asset, bmc_asset), candidate_ips=(bmc_asset.ip_address,), proposed_host_name=host_name_template.format(bmc=bmc_asset.ip_address), rules=(rule,), reasons=("Both active assets are currently unlinked.",)))
                proposed_ids.update((os_asset.id, bmc_asset.id))
                consumed_unlinked.update((os_asset.id, bmc_asset.id))

    # Every remaining active unlinked OS/BMC asset gets an explicit queue item.
    represented_unmatched = proposed_ids | conflict_ids | exceptions
    for asset in sorted(active, key=lambda item: (_ip_key(item.ip_address), item.id)):
        if asset.host_id is None and asset.id not in represented_unmatched:
            findings.append(_finding(inventory, kind="UNMATCHED_ASSET", assets=(asset,), reasons=("No unambiguous strong active counterpart was found.",)))

    states: dict[str, str] = {}
    for asset in active:
        if asset.id in exceptions:
            states[asset.id] = "EXCEPTION"
        elif asset.id in conflict_ids:
            states[asset.id] = "CONFLICT"
        elif asset.id in proposed_ids:
            states[asset.id] = "PROPOSED"
        elif asset.host_id is not None:
            states[asset.id] = "RESOLVED"
        else:
            states[asset.id] = "UNMATCHED"
    state_counts = {state: sum(1 for value in states.values() if value == state) for state in ("RESOLVED", "PROPOSED", "UNMATCHED", "CONFLICT", "EXCEPTION")}
    kpis: dict[str, int | float] = {
        "active_os_assets": sum(asset.asset_type == "OS" for asset in active),
        "active_bmc_assets": sum(asset.asset_type == "BMC" for asset in active),
        "os_attached_to_hosts": sum(asset.asset_type == "OS" and asset.host_id is not None for asset in active),
        "bmc_attached_to_hosts": sum(asset.asset_type == "BMC" and asset.host_id is not None for asset in active),
        "unresolved_os_assets": sum(asset.asset_type == "OS" and states[asset.id] in {"UNMATCHED", "CONFLICT"} for asset in active),
        "unresolved_bmc_assets": sum(asset.asset_type == "BMC" and states[asset.id] in {"UNMATCHED", "CONFLICT"} for asset in active),
        "proposed_host_creations": sum(finding.kind == "CREATE_HOST" for finding in findings),
        "incomplete_hosts": sum(bool(sides["OS"]) != bool(sides["BMC"]) for sides in by_host.values()),
        "conflicts": sum(finding.kind == "CONFLICT" for finding in findings),
        "explicit_exceptions": state_counts["EXCEPTION"],
        "discovered_rules": len(rules),
        "rule_support": sum(rule.support for rule in rules),
        "rule_contradictions": sum(rule.contradictions for rule in rules),
        "reconciliation_coverage": round((state_counts["RESOLVED"] + state_counts["PROPOSED"] + state_counts["EXCEPTION"]) * 100 / len(active), 2) if active else 100.0,
    }
    order = {"CREATE_HOST": 0, "COMPLETE_HOST": 1, "CONFLICT": 2, "UNMATCHED_ASSET": 3}
    findings.sort(key=lambda finding: (
        all(asset_id in deferred for asset_id in finding.asset_ids),
        order[finding.kind],
        finding.candidate_ips[0] if finding.candidate_ips else "",
        finding.proposal_id,
    ))
    return ReconciliationResult(rules=rules, findings=tuple(findings), states=states, kpis=kpis)  # type: ignore[arg-type]
