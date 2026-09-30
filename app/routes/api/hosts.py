from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import repository
from app.dependencies import get_connection

from .dependencies import require_editor
from .schemas import HostCreate, HostUpdate
from .utils import asset_payload, host_payload

router = APIRouter()


@router.get(
    "/hosts",
    summary="List hosts",
    description="Retrieve a list of all managed hosts (servers/machines) with vendor and notes.",
)
def list_hosts(connection=Depends(get_connection)):
    hosts = repository.list_hosts(connection)
    return [host_payload(host) for host in hosts]


@router.post("/hosts")
def create_host(
    payload: HostCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    vendor = (
        repository.get_vendor_by_id(connection, payload.vendor_id)
        if payload.vendor_id is not None
        else None
    )
    if payload.vendor_id is not None and vendor is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected vendor does not exist.",
        )
    host = repository.create_host(
        connection,
        name=payload.name,
        notes=payload.notes,
        vendor=vendor.name if vendor else None,
        current_user=_user,
    )
    return host_payload(host)


@router.get(
    "/hosts/{host_id}",
    summary="Get host details with linked IP assets",
    description="Retrieve a host by ID along with linked IP assets grouped by type (os, bmc, other).",
)
def get_host(host_id: int, connection=Depends(get_connection)):
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    return {
        **host_payload(host),
        "linked_assets": {
            "os": [asset_payload(asset) for asset in grouped["os"]],
            "bmc": [asset_payload(asset) for asset in grouped["bmc"]],
            "other": [asset_payload(asset) for asset in grouped["other"]],
        },
    }


@router.patch("/hosts/{host_id}")
def update_host(
    host_id: int,
    payload: HostUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    vendor = (
        repository.get_vendor_by_id(connection, payload.vendor_id)
        if payload.vendor_id is not None
        else None
    )
    if payload.vendor_id is not None and vendor is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected vendor does not exist.",
        )
    host = repository.update_host(
        connection,
        host_id=host_id,
        name=payload.name,
        notes=payload.notes,
        vendor=vendor.name if vendor else None,
    )
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return host_payload(host)
