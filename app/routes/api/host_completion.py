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
