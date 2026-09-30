from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app import repository
from app.dependencies import get_connection
from app.models import UserRole
from app.services import bmc_discovery

from .dependencies import (
    require_authenticated_api_or_ui_session,
)

router = APIRouter(prefix="/api/hosts/bmc-discovery", tags=["bmc-discovery"])


def require_writer_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    user = require_authenticated_api_or_ui_session(
        request=request,
        authorization=authorization,
        connection=connection,
    )
    if user.role not in {UserRole.EDITOR, UserRole.SUPERUSER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


class BMCScanRequest(BaseModel):
    host_ids: Optional[list[int]] = None
    timeout: float = Field(default=2.0, ge=0.5, le=10.0)
    concurrency: int = Field(default=20, ge=1, le=50)


class BMCApplyItem(BaseModel):
    host_id: int
    vendor_name: str


class BMCApplyRequest(BaseModel):
    items: list[BMCApplyItem]


@router.get(
    "/targets",
    summary="List hosts eligible for BMC discovery",
    description="Returns hosts with linked active BMC IP addresses that currently have no vendor assigned.",
)
def get_discovery_targets(
    host_id: Optional[list[int]] = Query(default=None),
    all_hosts: bool = Query(default=False),
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    targets = repository.get_bmc_discovery_targets(
        connection,
        host_ids=host_id,
        only_unassigned=not all_hosts,
    )
    return {"targets": targets, "total": len(targets)}


@router.post(
    "/scan",
    summary="Scan BMC addresses for vendor signatures",
    description="Probes BMC IP addresses on port 443 over SSL/TLS and extracts server vendor signatures.",
)
async def scan_bmc_vendors(
    payload: Optional[BMCScanRequest] = None,
    connection=Depends(get_connection),
    _user=Depends(require_authenticated_api_or_ui_session),
):
    req = payload or BMCScanRequest()
    targets = repository.get_bmc_discovery_targets(
        connection,
        host_ids=req.host_ids,
        only_unassigned=True if not req.host_ids else False,
    )
    if not targets:
        return {"results": [], "total": 0, "matched_count": 0}

    results = await bmc_discovery.scan_bmc_targets(
        targets,
        concurrency=req.concurrency,
        timeout=req.timeout,
    )
    matched_count = sum(1 for r in results if r.get("status") == "matched")

    return {
        "results": results,
        "total": len(results),
        "matched_count": matched_count,
    }


@router.post(
    "/apply",
    summary="Apply discovered vendors to hosts",
    description="Updates host vendor associations for selected candidates and creates missing vendors.",
)
def apply_bmc_vendors(
    payload: BMCApplyRequest,
    connection=Depends(get_connection),
    user=Depends(require_writer_user),
):
    if not payload.items:
        return {"applied": [], "count": 0}

    applied = bmc_discovery.apply_discovered_vendors(
        connection,
        [item.model_dump() for item in payload.items],
        current_user=user,
    )
    return {"applied": applied, "count": len(applied)}
