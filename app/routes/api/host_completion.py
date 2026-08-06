from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import get_connection
from app.services import host_completion

from .dependencies import require_editor_api_or_ui_session

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


@router.get("/analytics", response_model=HostCompletionAnalytics)
def get_host_completion_analytics(connection=Depends(get_connection)):
    """Return read-only completion counts and confirmed address patterns."""

    return host_completion.get_analytics(connection)


@router.get("/cases", response_model=HostCompletionCasesPage)
def list_host_completion_cases(
    missing: Literal["OS", "BMC", "any"] = "any",
    limit: int = Query(default=100, ge=1, le=500),
    cursor: Optional[int] = Query(default=None, ge=0),
    connection=Depends(get_connection),
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
):
    """List confirmed examples: Hosts with active OS and BMC assets."""

    return host_completion.list_confirmed_examples(
        connection,
        limit=limit,
        cursor=cursor,
    )


@router.get("/review-queue", response_model=HostCompletionReviewQueue)
def get_host_completion_review_queue(connection=Depends(get_connection)):
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
