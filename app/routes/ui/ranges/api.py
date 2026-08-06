from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies import get_connection
from app.routes.api.schemas import IPRangeCreate, IPRangeDelete, IPRangeUpdate
from app.routes.ui.utils import require_ui_editor

from . import repository
from .common import _build_range_table_rows

router = APIRouter()


def _range_payload(ip_range) -> dict[str, object]:
    return {
        "id": ip_range.id,
        "name": ip_range.name,
        "cidr": ip_range.cidr,
        "notes": ip_range.notes,
        "created_at": ip_range.created_at,
        "updated_at": ip_range.updated_at,
    }


@router.get("/api/ui/ranges")
def list_ranges_for_ui(connection=Depends(get_connection)):
    ranges = list(repository.list_ip_ranges(connection))
    utilization = repository.get_ip_range_utilization(connection)
    return {"ranges": _build_range_table_rows(ranges, utilization)}


@router.post("/api/ui/ranges", status_code=status.HTTP_201_CREATED)
def create_range_for_ui(
    payload: IPRangeCreate,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    try:
        ip_range = repository.create_ip_range(
            connection,
            name=payload.name,
            cidr=payload.cidr,
            notes=payload.notes,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CIDR already exists.",
        ) from exc
    return _range_payload(ip_range)


@router.patch("/api/ui/ranges/{range_id}")
def update_range_for_ui(
    range_id: int,
    payload: IPRangeUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    if repository.get_ip_range_by_id(connection, range_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP range not found.",
        )
    try:
        ip_range = repository.update_ip_range(
            connection,
            range_id,
            name=payload.name,
            cidr=payload.cidr,
            notes=payload.notes,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CIDR already exists.",
        ) from exc
    if ip_range is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP range not found.",
        )
    return _range_payload(ip_range)


@router.delete("/api/ui/ranges/{range_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_range_for_ui(
    range_id: int,
    payload: IPRangeDelete,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> Response:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP range not found.",
        )
    if payload.confirm_name.strip() != ip_range.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای حذف کامل، نام رنج را دقیقاً وارد کنید.",
        )
    if not repository.delete_ip_range(connection, range_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP range not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
