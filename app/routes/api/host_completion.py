from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.dependencies import get_connection
from app.services import host_completion

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
