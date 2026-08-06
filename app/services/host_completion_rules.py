from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Literal

RuleKind = Literal["prefix", "octet"]


@dataclass(frozen=True)
class Transformation:
    kind: RuleKind
    source_16: str
    source_prefix: str | None = None
    target_prefix: str | None = None
    prefix_length: int | None = None
    octet_index: int | None = None
    source_octet: int | None = None
    target_octet: int | None = None

    def apply(self, address: str) -> str | None:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return None
        if parsed.version != 4 or parsed not in ipaddress.ip_network(self.source_16):
            return None

        if self.kind == "prefix":
            assert self.prefix_length is not None
            assert self.source_prefix is not None
            assert self.target_prefix is not None
            source = ipaddress.ip_network(self.source_prefix)
            if parsed not in source:
                return None
            target = ipaddress.ip_network(self.target_prefix)
            host_mask = (1 << (32 - self.prefix_length)) - 1
            return str(
                ipaddress.ip_address(
                    int(target.network_address) | (int(parsed) & host_mask)
                )
            )

        assert self.octet_index is not None
        assert self.source_octet is not None
        assert self.target_octet is not None
        octets = list(parsed.packed)
        if octets[self.octet_index] != self.source_octet:
            return None
        octets[self.octet_index] = self.target_octet
        return str(ipaddress.ip_address(bytes(octets)))

    @property
    def description(self) -> str:
        if self.kind == "prefix":
            return f"{self.source_prefix} -> {self.target_prefix}"
        assert self.octet_index is not None
        return (
            f"octet {self.octet_index + 1} replacement "
            f"{self.source_octet} -> {self.target_octet} in {self.source_16}"
        )


@dataclass(frozen=True)
class CompletionRule:
    transformation: Transformation
    support: int
    contradictions: int
    rejected: int
    confidence: float
    evidence: tuple[str, ...]


def _ipv4_pair(
    os_ip: str, bmc_ip: str
) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address] | None:
    try:
        source = ipaddress.ip_address(os_ip)
        target = ipaddress.ip_address(bmc_ip)
    except ValueError:
        return None
    if source.version != 4 or target.version != 4:
        return None
    return source, target


def _pair_transformations(os_ip: str, bmc_ip: str) -> set[Transformation]:
    pair = _ipv4_pair(os_ip, bmc_ip)
    if pair is None:
        return set()
    source, target = pair
    source_16 = str(ipaddress.ip_network(f"{source}/16", strict=False))
    candidates: set[Transformation] = set()

    for prefix_length in (16, 24):
        host_mask = (1 << (32 - prefix_length)) - 1
        if int(source) & host_mask != int(target) & host_mask:
            continue
        candidates.add(
            Transformation(
                kind="prefix",
                source_16=source_16,
                source_prefix=str(
                    ipaddress.ip_network(f"{source}/{prefix_length}", strict=False)
                ),
                target_prefix=str(
                    ipaddress.ip_network(f"{target}/{prefix_length}", strict=False)
                ),
                prefix_length=prefix_length,
            )
        )

    source_octets = list(source.packed)
    target_octets = list(target.packed)
    differing = [
        index
        for index, (source_value, target_value) in enumerate(
            zip(source_octets, target_octets)
        )
        if source_value != target_value
    ]
    if len(differing) == 1:
        index = differing[0]
        candidates.add(
            Transformation(
                kind="octet",
                source_16=source_16,
                octet_index=index,
                source_octet=source_octets[index],
                target_octet=target_octets[index],
            )
        )
    return candidates


def infer_rules(
    confirmed_pairs: Iterable[tuple[str, str]],
    *,
    rejected_candidates: Iterable[tuple[str, str]] = (),
    min_support: int = 3,
) -> list[CompletionRule]:
    """Infer active deterministic transformations from confirmed IPv4 pairs."""

    pairs = list(confirmed_pairs)
    rejects = list(rejected_candidates)
    candidates = {
        candidate
        for os_ip, bmc_ip in pairs
        for candidate in _pair_transformations(os_ip, bmc_ip)
    }
    rules: list[CompletionRule] = []
    for candidate in candidates:
        scoped_pairs = [
            pair
            for pair in pairs
            if _ipv4_pair(*pair) is not None
            and str(ipaddress.ip_network(f"{pair[0]}/16", strict=False))
            == candidate.source_16
        ]
        matching = [
            pair for pair in scoped_pairs if candidate.apply(pair[0]) == pair[1]
        ]
        support = len(matching)
        if support < min_support:
            continue
        confirmed_contradictions = len(scoped_pairs) - support
        rejected = sum(
            1
            for os_ip, candidate_ip in rejects
            if candidate.apply(os_ip) == candidate_ip
        )
        contradictions = confirmed_contradictions + rejected
        confidence = min(
            support / (support + contradictions + 1) + min(support / 20, 0.1),
            1.0,
        )
        rules.append(
            CompletionRule(
                transformation=candidate,
                support=support,
                contradictions=contradictions,
                rejected=rejected,
                confidence=confidence,
                evidence=tuple(f"{os_ip} -> {bmc_ip}" for os_ip, bmc_ip in matching),
            )
        )
    rules.sort(
        key=lambda rule: (
            -rule.confidence,
            -rule.support,
            rule.transformation.description,
        )
    )
    return rules
