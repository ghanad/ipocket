from __future__ import annotations

import math
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType, UserRole
from app.routes.api.schemas import UIHostDelete, UIHostWrite
from app.routes.ui.utils import (
    _collect_inline_ip_errors,
    _is_auto_host_for_bmc_enabled,
    get_optional_current_ui_user,
)
from app.utils import normalize_tag_names

from .common import (
    build_host_detail_payload,
    normalize_per_page,
    require_ui_host_writer,
)

router = APIRouter()


def _metadata_payload(connection) -> dict[str, list[dict[str, object]]]:
    return {
        "projects": [
            {"id": item.id, "name": item.name, "color": item.color}
            for item in repository.list_projects(connection)
        ],
        "vendors": [
            {"id": item.id, "name": item.name}
            for item in repository.list_vendors(connection)
        ],
        "tags": [
            {"id": item.id, "name": item.name, "color": item.color}
            for item in repository.list_tags(connection)
        ],
    }


def _validate_references(connection, payload: UIHostWrite):
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
    projects = list(repository.list_projects(connection))
    if payload.project_id is not None and all(
        project.id != payload.project_id for project in projects
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected project does not exist.",
        )
    return vendor


def _validate_ips(connection, host_id: Optional[int], payload: UIHostWrite):
    errors, to_create, to_update = _collect_inline_ip_errors(
        connection, host_id, payload.os_ips, payload.bmc_ips
    )
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )
    return to_create, to_update


def _apply_inline_ips(
    connection,
    host_id: int,
    project_id: Optional[int],
    to_create,
    to_update,
) -> None:
    for ip_address, asset_type in to_create:
        repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=asset_type,
            project_id=project_id,
            host_id=host_id,
            notes=None,
            tags=[],
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
        )
    for ip_address, asset_type in to_update:
        repository.update_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=asset_type,
            project_id=project_id,
            project_id_provided=True,
            host_id=host_id,
        )


@router.get("/api/ui/hosts")
def list_hosts_for_ui(
    q: Optional[str] = None,
    vendor_id: Optional[int] = None,
    project_id: Optional[str] = None,
    tag: Optional[list[str]] = Query(default=None),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, alias="per-page"),
    connection=Depends(get_connection),
    user=Depends(get_optional_current_ui_user),
):
    per_page = normalize_per_page(per_page)
    project_value = (project_id or "").strip()
    project_unassigned = project_value == "unassigned"
    parsed_project_id: Optional[int] = None
    if project_value and not project_unassigned:
        try:
            parsed_project_id = int(project_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Select a valid project."
            ) from exc
    normalized_status = (status_filter or "").strip().lower()
    if normalized_status not in {"linked", "free"}:
        normalized_status = ""
    try:
        tags = normalize_tag_names(tag or [])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    filters = {
        "query_text": (q or "").strip() or None,
        "vendor_id": vendor_id,
        "project_id": parsed_project_id,
        "project_unassigned_only": project_unassigned,
        "asset_type": None,
        "unassigned_only": unassigned_only,
        "status_filter": normalized_status or None,
        "tag_names": tags,
    }
    total = repository.count_hosts(connection, **filters)
    total_pages = max(1, math.ceil(total / per_page)) if total else 1
    page = min(page, total_pages)
    rows = repository.list_hosts_with_ip_counts_paginated(
        connection,
        limit=per_page,
        offset=(page - 1) * per_page if total else 0,
        **filters,
    )
    return {
        "hosts": rows,
        "filters": _metadata_payload(connection),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
        "can_edit": bool(user and user.role in {UserRole.EDITOR, UserRole.SUPERUSER}),
    }


@router.get("/api/ui/hosts/{host_id}/detail")
def get_host_detail_for_ui(
    host_id: int,
    connection=Depends(get_connection),
):
    payload = build_host_detail_payload(connection, host_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Host not found.")
    return payload


@router.post("/api/ui/hosts", status_code=status.HTTP_201_CREATED)
def create_host_for_ui(
    payload: UIHostWrite,
    connection=Depends(get_connection),
    _user=Depends(require_ui_host_writer),
):
    vendor = _validate_references(connection, payload)
    to_create, to_update = _validate_ips(connection, None, payload)
    try:
        host = repository.create_host(
            connection,
            name=payload.name,
            notes=payload.notes,
            vendor=vendor.name if vendor else None,
        )
        _apply_inline_ips(connection, host.id, payload.project_id, to_create, to_update)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Host name already exists."
        ) from exc
    return {"id": host.id, "name": host.name}


@router.patch("/api/ui/hosts/{host_id}")
def update_host_for_ui(
    host_id: int,
    payload: UIHostWrite,
    connection=Depends(get_connection),
    _user=Depends(require_ui_host_writer),
):
    if repository.get_host_by_id(connection, host_id) is None:
        raise HTTPException(status_code=404, detail="Host not found.")
    vendor = _validate_references(connection, payload)
    to_create, to_update = _validate_ips(connection, host_id, payload)
    try:
        updated = repository.update_host(
            connection,
            host_id=host_id,
            name=payload.name,
            notes=payload.notes,
            notes_provided=True,
            vendor=vendor.name if vendor else None,
            vendor_provided=True,
        )
        linked = repository.get_host_linked_assets_grouped(connection, host_id)
        requested = {
            IPAssetType.OS: set(payload.os_ips),
            IPAssetType.BMC: set(payload.bmc_ips),
        }
        removed_assets = [
            asset
            for asset_type, group_name in (
                (IPAssetType.OS, "os"),
                (IPAssetType.BMC, "bmc"),
            )
            for asset in linked[group_name]
            if asset.ip_address not in requested[asset_type]
        ]
        for asset in removed_assets:
            repository.update_ip_asset(
                connection,
                ip_address=asset.ip_address,
                host_id=None,
                host_id_provided=True,
            )
        linked = repository.get_host_linked_assets_grouped(connection, host_id)
        linked_ids = [asset.id for group in linked.values() for asset in group]
        if linked_ids and "project_id" in payload.model_fields_set:
            repository.bulk_update_ip_assets(
                connection,
                linked_ids,
                project_id=payload.project_id,
                set_project_id=True,
            )
        _apply_inline_ips(connection, host_id, payload.project_id, to_create, to_update)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Host name already exists."
        ) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Host not found.")
    return {"id": updated.id, "name": updated.name}


@router.delete("/api/ui/hosts/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host_for_ui(
    host_id: int,
    payload: UIHostDelete,
    connection=Depends(get_connection),
    _user=Depends(require_ui_host_writer),
) -> Response:
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found.")
    if payload.confirm_name.strip() != host.name:
        raise HTTPException(
            status_code=400,
            detail="برای حذف کامل، نام Host را دقیقاً وارد کنید.",
        )
    if not repository.delete_host(connection, host_id):
        raise HTTPException(status_code=404, detail="Host not found.")
    return Response(status_code=204)
