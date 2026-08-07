"""Deterministic, read-only host/IP reconciliation primitives.

The package deliberately has no dependency on :mod:`app`, its repositories, or
SQLAlchemy.  An ipocket adapter supplies a current :class:`Inventory`, then
applies an operator-approved finding through the normal ipocket API.
"""

from .engine import discover_rules, proposal_is_current, reconcile
from .models import (
    AgentDecision,
    Asset,
    AssetType,
    Finding,
    FindingKind,
    Host,
    Inventory,
    ReconciliationResult,
    ReconciliationState,
    Rule,
    RuleStrength,
)

__all__ = [
    "AgentDecision",
    "Asset",
    "AssetType",
    "Finding",
    "FindingKind",
    "Host",
    "Inventory",
    "ReconciliationResult",
    "ReconciliationState",
    "Rule",
    "RuleStrength",
    "discover_rules",
    "proposal_is_current",
    "reconcile",
]
