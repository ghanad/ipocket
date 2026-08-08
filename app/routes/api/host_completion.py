from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_connection
from app.services import host_completion, host_reconciliation

from .dependencies import (
    require_authenticated_api_or_ui_session,
    require_editor_api_or_ui_session,
    require_superuser_api_or_ui_session,
)

router = APIRouter(prefix="/api/host-completion", tags=["host-completion"])


class HostCompletionAsset(BaseModel):
    id: int
    ip_address: str
    project_id: Optional[int]
    project_name: Optional[str]


class HostCompletionRecord(BaseModel):
    host_id: int
    host_name: str
    vendor: Optional[str]
    os_assets: list[HostCompletionAsset]
    bmc_assets: list[HostCompletionAsset]


class HostCompletionCase(HostCompletionRecord):
    missing: Literal["OS", "BMC"]


class HostCompletionCasesPage(BaseModel):
    items: list[HostCompletionCase]
    next_cursor: Optional[int]


class HostCompletionExamplesPage(BaseModel):
    items: list[HostCompletionRecord]
    next_cursor: Optional[int]


class HostCompletionBreakdown(BaseModel):
    os_only: int
    bmc_only: int
    unlinked: int


class HostCompletionPattern(BaseModel):
    source_prefix: str
    target_prefix: str
    support: int
    contradictions: int
    coverage_percent: float


class HostCompletionIPTypeCounts(BaseModel):
    BMC: int
    OS: int
    VM: int
    unknown: int


class HostCompletionAnalytics(BaseModel):
    total_hosts: int
    complete_hosts: int
    incomplete_hosts: int
    breakdown: HostCompletionBreakdown
    confirmed_pairs: int
    patterns: list[HostCompletionPattern]
    ip_type_counts: HostCompletionIPTypeCounts
    untyped_active: int
    unlinked_os: int
    unlinked_bmc: int
    hosts_missing_bmc: int
    hosts_missing_os: int
    inventory_health_percent: float


class HostCompletionQueueAsset(BaseModel):
    address: str
    hostname: Optional[str] = None


class HostCompletionReviewItem(BaseModel):
    case_type: Literal[
        "UNLINKED_OS_PAIR",
        "UNLINKED_BMC_PAIR",
        "UNLINKED_OS",
        "UNLINKED_BMC",
        "HOST_MISSING_BMC",
        "HOST_MISSING_OS",
    ]
    mode: Literal["SUGGEST", "ASK"]
    host_id: Optional[int] = None
    os_asset: Optional[HostCompletionQueueAsset] = None
    bmc_asset: Optional[HostCompletionQueueAsset] = None
    would_create_host: bool
    candidate_ip: Optional[str] = None
    confidence: Optional[float] = None
    evidence: list[str]
    reason_text: str
    host_name_template: str
    host_options: list["HostCompletionHostOption"]


class HostCompletionHostOption(BaseModel):
    id: int
    name: str
    has_os: bool
    has_bmc: bool


class HostCompletionReviewQueue(BaseModel):
    item: Optional[HostCompletionReviewItem]
    remaining: int


class HostCompletionDecisionRequest(BaseModel):
    case_type: Literal[
        "UNLINKED_OS_PAIR",
        "UNLINKED_BMC_PAIR",
        "UNLINKED_OS",
        "UNLINKED_BMC",
        "HOST_MISSING_BMC",
        "HOST_MISSING_OS",
    ] = "HOST_MISSING_BMC"
    mode: Literal["SUGGEST", "ASK"]
    host_id: Optional[int] = None
    os_address: Optional[str] = None
    bmc_address: Optional[str] = None
    decision: Literal[
        "ACCEPT",
        "REJECT",
        "CORRECTED",
        "UNSURE",
        "NO_BMC",
        "NO_OS",
        "CREATE_HOST_ONLY",
        "ATTACH_EXISTING",
        "DEACTIVATE",
    ]
    candidate_ip: Optional[str] = None
    corrected_ip: Optional[str] = None
    target_host_id: Optional[int] = None
    host_name: Optional[str] = None


class HostCompletionDecisionResponse(BaseModel):
    id: int
    decision: str
    applied_ip: Optional[str]
    host_id: Optional[int]
    message: Optional[str] = None


class ReconciliationDecisionRequest(BaseModel):
    proposal_id: str
    inventory_fingerprint: str
    decision: Literal[
        "ACCEPT",
        "CORRECT",
        "WRONG_PAIR",
        "UNSURE",
        "EXCEPTION",
        "ATTACH_EXISTING",
        "DEACTIVATE",
    ]
    target_host_id: Optional[int] = None
    counterpart_ip: Optional[str] = None
    counterpart_type: Optional[Literal["OS", "BMC"]] = None


class ReconciliationDecisionResponse(BaseModel):
    id: int
    decision: str
    host_id: Optional[int]
    proposal_id: str
    idempotent_replay: bool


class ManualRuleRequest(BaseModel):
    source_prefix: str
    target_prefix: str
    active: bool = True
    notes: Optional[str] = None


class ManualRuleResponse(BaseModel):
    id: int
    source_prefix: str
    target_prefix: str
    prefix_length: Literal[16, 24]
    active: bool
    notes: Optional[str]


@router.get("/analytics", response_model=HostCompletionAnalytics)
def get_host_completion_analytics(
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """Return read-only completion counts and confirmed address patterns."""

    return host_completion.get_analytics(connection)


@router.get("/cases", response_model=HostCompletionCasesPage)
def list_host_completion_cases(
    missing: Literal["OS", "BMC", "any"] = "any",
    limit: int = Query(default=100, ge=1, le=500),
    cursor: Optional[int] = Query(default=None, ge=0),
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """List Hosts that have exactly one side of their active OS/BMC pair."""

    return host_completion.list_incomplete_hosts(
        connection,
        missing=missing,
        limit=limit,
        cursor=cursor,
    )


@router.get("/examples", response_model=HostCompletionExamplesPage)
def list_host_completion_examples(
    limit: int = Query(default=100, ge=1, le=500),
    cursor: Optional[int] = Query(default=None, ge=0),
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """List confirmed examples: Hosts with active OS and BMC assets."""

    return host_completion.list_confirmed_examples(
        connection,
        limit=limit,
        cursor=cursor,
    )


@router.get("/review-queue", response_model=HostCompletionReviewQueue)
def get_host_completion_review_queue(
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """Return the next deterministic Host-completion review item."""

    return host_completion.build_review_queue(connection)


@router.post("/decisions", response_model=HostCompletionDecisionResponse)
def create_host_completion_decision(
    payload: HostCompletionDecisionRequest,
    connection=Depends(get_connection),
    user=Depends(require_editor_api_or_ui_session),
):
    """Record operator feedback and apply accepted BMC links through asset services."""

    try:
        return host_completion.record_decision(
            connection,
            case_type=payload.case_type,
            mode=payload.mode,
            host_id=payload.host_id,
            os_address=payload.os_address,
            bmc_address=payload.bmc_address,
            decision=payload.decision,
            candidate_ip=payload.candidate_ip,
            corrected_ip=payload.corrected_ip,
            target_host_id=payload.target_host_id,
            host_name=payload.host_name,
            user=user,
        )
    except host_completion.HostCompletionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/findings")
def list_reconciliation_findings(
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """Return the deterministic reconciliation queue from the current inventory."""

    return host_reconciliation.list_findings(connection)


@router.get("/findings/next")
def get_next_reconciliation_finding(
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """Return the highest-value current finding and the remaining count."""

    return host_reconciliation.next_finding(connection)


@router.get("/summary")
def get_reconciliation_summary(
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    """Return reconciliation states, KPIs, and explainable discovered rules."""

    return host_reconciliation.get_summary(connection)


@router.post("/rules", response_model=ManualRuleResponse, status_code=201)
def create_manual_reconciliation_rule(
    payload: ManualRuleRequest,
    connection=Depends(get_connection),
    user=Depends(require_superuser_api_or_ui_session),
):
    """Create an administrator-owned, deterministic OS-to-BMC mapping."""

    try:
        return host_reconciliation.create_manual_rule(
            connection,
            source_prefix=payload.source_prefix,
            target_prefix=payload.target_prefix,
            active=payload.active,
            notes=payload.notes,
            user=user,
        )
    except host_reconciliation.ReconciliationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.put("/rules/{rule_id}", response_model=ManualRuleResponse)
def update_manual_reconciliation_rule(
    rule_id: int,
    payload: ManualRuleRequest,
    connection=Depends(get_connection),
    user=Depends(require_superuser_api_or_ui_session),
):
    """Update or deactivate a manual rule while retaining its audit history."""

    try:
        return host_reconciliation.update_manual_rule(
            connection,
            rule_id=rule_id,
            source_prefix=payload.source_prefix,
            target_prefix=payload.target_prefix,
            active=payload.active,
            notes=payload.notes,
            user=user,
        )
    except host_reconciliation.ReconciliationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/findings/decisions",
    response_model=ReconciliationDecisionResponse,
)
def apply_reconciliation_decision(
    payload: ReconciliationDecisionRequest,
    connection=Depends(get_connection),
    user=Depends(require_editor_api_or_ui_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Apply an Editor decision after stale-state validation."""

    try:
        return host_reconciliation.apply_decision(
            connection,
            proposal_id=payload.proposal_id,
            inventory_fingerprint=payload.inventory_fingerprint,
            decision=payload.decision,
            target_host_id=payload.target_host_id,
            counterpart_ip=payload.counterpart_ip,
            counterpart_type=payload.counterpart_type,
            idempotency_key=idempotency_key,
            user=user,
        )
    except host_reconciliation.ReconciliationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
