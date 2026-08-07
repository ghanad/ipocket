from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AssetType = Literal["OS", "BMC", "VM", "VIP", "OTHER"]
FindingKind = Literal["CREATE_HOST", "COMPLETE_HOST", "UNMATCHED_ASSET", "CONFLICT"]
ReconciliationState = Literal[
    "RESOLVED", "PROPOSED", "UNMATCHED", "CONFLICT", "EXCEPTION"
]
DecisionKind = Literal[
    "ACCEPT",
    "CORRECT",
    "WRONG_PAIR",
    "UNSURE",
    "EXCEPTION",
    "ATTACH_EXISTING",
    "ARCHIVE",
]
RuleKind = Literal["PREFIX_16", "PREFIX_24", "OCTET"]
RuleStrength = Literal["STRONG", "MODERATE", "WEAK", "INACTIVE"]


@dataclass(frozen=True)
class Asset:
    """A small, API-friendly projection of an authoritative IP Asset."""

    id: str
    ip_address: str
    asset_type: AssetType
    host_id: str | None = None
    archived: bool = False


@dataclass(frozen=True)
class Host:
    id: str
    name: str


@dataclass(frozen=True)
class AgentDecision:
    """Non-authoritative operator feedback retained by the agent adapter.

    ``WRONG_PAIR`` requires both addresses and is the only feedback type that
    acts as negative evidence.  ``UNSURE`` and ``EXCEPTION`` intentionally do
    not make a discovered network rule weaker.
    """

    kind: DecisionKind
    os_ip: str | None = None
    bmc_ip: str | None = None
    asset_id: str | None = None


@dataclass(frozen=True)
class Inventory:
    assets: tuple[Asset, ...]
    hosts: tuple[Host, ...]
    decisions: tuple[AgentDecision, ...] = ()

    def __post_init__(self) -> None:
        if len({asset.id for asset in self.assets}) != len(self.assets):
            raise ValueError("Asset IDs must be unique.")
        if len({host.id for host in self.hosts}) != len(self.hosts):
            raise ValueError("Host IDs must be unique.")


@dataclass(frozen=True)
class Transformation:
    """An extensible deterministic IPv4 transformation in the OS → BMC direction."""

    kind: RuleKind
    source: str
    target: str
    octet_index: int | None = None
    source_scope: str | None = None
    target_scope: str | None = None

    @property
    def description(self) -> str:
        if self.kind == "OCTET":
            return (
                f"octet {self.octet_index!s} {self.source} -> {self.target} "
                f"in {self.source_scope}"
            )
        return f"{self.source} -> {self.target}"


@dataclass(frozen=True)
class Rule:
    id: str
    transformation: Transformation
    direction: Literal["OS_TO_BMC"] = "OS_TO_BMC"
    support: int = 0
    contradictions: int = 0
    examples: tuple[tuple[str, str], ...] = ()
    active: bool = False
    strength: RuleStrength = "INACTIVE"


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    proposal_id: str
    inventory_fingerprint: str
    asset_ids: tuple[str, ...]
    host_id: str | None = None
    candidate_ips: tuple[str, ...] = ()
    proposed_host_name: str | None = None
    rule_ids: tuple[str, ...] = ()
    strength: RuleStrength | None = None
    evidence: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    # Kept so callers can reject a stale proposal without knowing application
    # internals.  The field is intentionally a compact, deterministic snapshot.
    assumptions: tuple[tuple[str, ...], ...] = field(default_factory=tuple, repr=False)


@dataclass(frozen=True)
class ReconciliationResult:
    rules: tuple[Rule, ...]
    findings: tuple[Finding, ...]
    states: dict[str, ReconciliationState]
    kpis: dict[str, int | float]
