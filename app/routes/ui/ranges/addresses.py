from __future__ import annotations

import sqlite3
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_connection
from app.models import IPAssetType, UserRole
from app.routes.api.schemas import UIRangeAddressCreate, UIRangeAddressWrite
from app.routes.ui.utils import (
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int,
    _parse_optional_int_query,
    _parse_optional_str,
    _parse_positive_int_query,
    _render_template,
    get_optional_current_ui_user,
    require_ui_editor,
)
from app.utils import normalize_tag_names, validate_ip_address

from . import repository
from .common import _parse_selected_tags

router = APIRouter()

_ALLOWED_PAGE_SIZES = {10, 20, 50, 100}
_DEFAULT_PAGE_SIZE = 20
_ALLOWED_STATUS_FILTERS = {"all", "used", "free"}


def _normalize_status_filter(value: Optional[str]) -> str:
    normalized = (value or "all").strip().lower()
    if normalized not in _ALLOWED_STATUS_FILTERS:
        return "all"
    return normalized


def _can_write(user) -> bool:
    return bool(user and user.role == UserRole.EDITOR)


def _normalized_range_query(request: Request, connection) -> dict[str, Any]:
    projects = list(repository.list_projects(connection))
    tags = list(repository.list_tags(connection))
    project_ids = {project.id for project in projects}
    tag_names = {tag.name for tag in tags}

    per_page = _parse_positive_int_query(
        request.query_params.get("per-page"), _DEFAULT_PAGE_SIZE
    )
    if per_page not in _ALLOWED_PAGE_SIZES:
        per_page = _DEFAULT_PAGE_SIZE
    page = _parse_positive_int_query(request.query_params.get("page"), 1)
    status_filter = _normalize_status_filter(request.query_params.get("status"))
    ip_query = (request.query_params.get("q") or "").strip()
    project_value = (request.query_params.get("project_id") or "").strip()
    project_unassigned = project_value == "unassigned"
    project_id = (
        None if project_unassigned else _parse_optional_int_query(project_value)
    )
    if project_id not in project_ids:
        project_id = None
        if not project_unassigned:
            project_value = ""
    raw_tags = request.query_params.getlist("tag")
    try:
        selected_tags = normalize_tag_names(raw_tags) if raw_tags else []
    except ValueError:
        selected_tags = []
    selected_tags = [tag for tag in selected_tags if tag in tag_names]
    try:
        asset_type = _normalize_asset_type(request.query_params.get("type"))
    except ValueError:
        asset_type = None

    return {
        "q": ip_query,
        "project_id": "unassigned"
        if project_unassigned
        else str(project_id or ""),
        "parsed_project_id": project_id,
        "project_unassigned": project_unassigned,
        "type": asset_type.value if asset_type else "",
        "asset_type": asset_type,
        "tags": selected_tags,
        "status": status_filter,
        "page": page,
        "per_page": per_page,
        "projects": projects,
        "tag_catalog": tags,
    }


def _range_addresses_payload(
    request: Request,
    range_id: int,
    connection,
    user,
) -> dict[str, Any]:
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    query = _normalized_range_query(request, connection)
    addresses = list(breakdown["addresses"])
    if query["status"] != "all":
        addresses = [
            row for row in addresses if row.get("status") == query["status"]
        ]
    if query["q"]:
        needle = query["q"].lower()
        addresses = [
            row
            for row in addresses
            if needle in str(row.get("ip_address") or "").lower()
        ]
    if query["project_unassigned"]:
        addresses = [
            row
            for row in addresses
            if row.get("status") == "used" and row.get("project_unassigned")
        ]
    elif query["parsed_project_id"] is not None:
        addresses = [
            row
            for row in addresses
            if row.get("status") == "used"
            and row.get("project_id") == query["parsed_project_id"]
        ]
    if query["asset_type"] is not None:
        addresses = [
            row
            for row in addresses
            if row.get("status") == "used"
            and row.get("asset_type") == query["asset_type"].value
        ]
    if query["tags"]:
        selected = set(query["tags"])
        addresses = [
            row
            for row in addresses
            if row.get("status") == "used"
            and any(tag.get("name") in selected for tag in row.get("tags") or [])
        ]

    total = len(addresses)
    total_pages = max(1, (total + query["per_page"] - 1) // query["per_page"])
    page = min(query["page"], total_pages)
    start = (page - 1) * query["per_page"]
    can_write = _can_write(user)
    rows = []
    for row in addresses[start : start + query["per_page"]]:
        row_payload = dict(row)
        row_payload["policy"] = {
            "can_add": can_write and row.get("status") == "free",
            "can_edit": can_write
            and row.get("status") == "used"
            and row.get("asset_id") is not None,
        }
        rows.append(row_payload)

    ip_range = breakdown["ip_range"]
    return {
        "range": {
            "id": ip_range.id,
            "name": ip_range.name,
            "cidr": ip_range.cidr,
            "total_usable": breakdown["total_usable"],
            "used": breakdown["used"],
            "free": breakdown["free"],
        },
        "filters": {
            "projects": [
                {"id": project.id, "name": project.name, "color": project.color}
                for project in query["projects"]
            ],
            "tags": [
                {"id": tag.id, "name": tag.name, "color": tag.color}
                for tag in query["tag_catalog"]
            ],
            "types": [asset_type.value for asset_type in IPAssetType],
            "policy": {"can_write": can_write},
        },
        "addresses": rows,
        "query": {
            "q": query["q"],
            "project_id": query["project_id"],
            "type": query["type"],
            "tags": query["tags"],
            "status": query["status"],
            "page": page,
            "per_page": query["per_page"],
        },
        "pagination": {
            "page": page,
            "per_page": query["per_page"],
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "start_index": start + 1 if total else 0,
            "end_index": min(start + query["per_page"], total) if total else 0,
        },
    }


def _validate_range_address_write(
    connection,
    range_id: int,
    *,
    ip_address: Optional[str],
    asset_type: Optional[str],
    project_id: Optional[int],
    tags_raw: list[str],
    require_free: bool,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not ip_address:
        errors.append("IP address is required.")
    else:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(str(exc.detail))
    normalized_type = None
    try:
        normalized_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_type is None and "Asset type is required." not in errors:
        errors.append("Asset type is required.")
    projects = list(repository.list_projects(connection))
    if project_id is not None and not any(
        project.id == project_id for project in projects
    ):
        errors.append("Selected project does not exist.")
    tags, tag_errors = _parse_selected_tags(connection, tags_raw)
    errors.extend(tag_errors)
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    address_lookup = {row["ip_address"]: row for row in breakdown["addresses"]}
    if ip_address and ip_address not in address_lookup:
        errors.append("IP address is not part of this range.")
    elif (
        require_free
        and ip_address
        and address_lookup[ip_address]["status"] != "free"
    ):
        errors.append("IP address is already assigned.")
    return {"asset_type": normalized_type, "tags": tags}, errors


def _render_range_addresses(
    request: Request,
    range_id: int,
    connection,
    errors: Optional[list[str]] = None,
    status_code: int = 200,
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    context = {
        "title": "ipocket - Range Addresses",
        "ip_range": ip_range,
        "initial_query": request.url.query,
        "errors": errors or [],
    }
    return _render_template(
        request,
        "range_addresses.html",
        context,
        status_code=status_code,
        active_nav="ranges",
    )


@router.get("/ui/ranges/{range_id}/addresses", response_class=HTMLResponse)
def ui_range_addresses(
    request: Request,
    range_id: int,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    asset_type: Optional[str] = Query(default=None, alias="type"),
    tag: Optional[list[str]] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
) -> HTMLResponse:
    _ = (q, project_id, asset_type, tag, status_filter, page, per_page)
    return _render_range_addresses(request, range_id, connection)


@router.post("/ui/ranges/{range_id}/addresses/add", response_class=HTMLResponse)
async def ui_range_quick_add_address(
    range_id: int,
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await request.form()
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = [str(tag) for tag in form_data.getlist("tags")]
    validated, errors = _validate_range_address_write(
        connection,
        range_id,
        ip_address=str(ip_address) if ip_address else None,
        asset_type=str(asset_type) if asset_type else None,
        project_id=project_id,
        tags_raw=tags_raw,
        require_free=True,
    )

    if errors:
        return _render_range_addresses(
            request,
            range_id,
            connection,
            errors=errors,
            status_code=400,
        )

    try:
        repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=validated["asset_type"],
            project_id=project_id,
            notes=notes,
            tags=validated["tags"],
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError:
        errors.append("IP address already exists.")

    if errors:
        return _render_range_addresses(
            request,
            range_id,
            connection,
            errors=errors,
            status_code=409,
        )

    ip_anchor = (ip_address or "").replace(".", "-").replace(":", "-")
    return RedirectResponse(
        url=f"/ui/ranges/{range_id}/addresses#ip-{ip_anchor}",
        status_code=303,
    )


@router.post(
    "/ui/ranges/{range_id}/addresses/{asset_id}/edit", response_class=HTMLResponse
)
async def ui_range_quick_edit_address(
    range_id: int,
    asset_id: int,
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> HTMLResponse:
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=404, detail="IP asset not found.")

    range_entry = next(
        (entry for entry in breakdown["addresses"] if entry["asset_id"] == asset.id),
        None,
    )
    if range_entry is None:
        raise HTTPException(status_code=404, detail="IP asset not found in this range.")

    form_data = await request.form()
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = [str(tag) for tag in form_data.getlist("tags")]
    validated, errors = _validate_range_address_write(
        connection,
        range_id,
        ip_address=asset.ip_address,
        asset_type=str(asset_type) if asset_type else None,
        project_id=project_id,
        tags_raw=tags_raw,
        require_free=False,
    )

    if errors:
        return _render_range_addresses(
            request,
            range_id,
            connection,
            errors=errors,
            status_code=400,
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=validated["asset_type"],
        project_id=project_id,
        project_id_provided=True,
        notes=notes,
        tags=validated["tags"],
        current_user=user,
        notes_provided=True,
    )

    ip_anchor = asset.ip_address.replace(".", "-").replace(":", "-")
    return RedirectResponse(
        url=f"/ui/ranges/{range_id}/addresses#ip-{ip_anchor}",
        status_code=303,
    )


@router.get("/api/ui/ranges/{range_id}/addresses")
def list_range_addresses_for_ui(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    user=Depends(get_optional_current_ui_user),
):
    return _range_addresses_payload(request, range_id, connection, user)


@router.post("/api/ui/ranges/{range_id}/addresses", status_code=201)
def create_range_address_for_ui(
    range_id: int,
    payload: UIRangeAddressCreate,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    validated, errors = _validate_range_address_write(
        connection,
        range_id,
        ip_address=payload.ip_address,
        asset_type=payload.type,
        project_id=payload.project_id,
        tags_raw=payload.tags,
        require_free=True,
    )
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=payload.ip_address,
            asset_type=validated["asset_type"],
            project_id=payload.project_id,
            notes=_parse_optional_str(payload.notes),
            tags=validated["tags"],
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail=["IP address already exists."]
        ) from exc
    return {"asset_id": asset.id, "ip_address": asset.ip_address}


@router.patch("/api/ui/ranges/{range_id}/addresses/{asset_id}")
def update_range_address_for_ui(
    range_id: int,
    asset_id: int,
    payload: UIRangeAddressWrite,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=404, detail="IP asset not found.")
    if not any(row.get("asset_id") == asset.id for row in breakdown["addresses"]):
        raise HTTPException(status_code=404, detail="IP asset not found in this range.")
    validated, errors = _validate_range_address_write(
        connection,
        range_id,
        ip_address=asset.ip_address,
        asset_type=payload.type,
        project_id=payload.project_id,
        tags_raw=payload.tags,
        require_free=False,
    )
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    updated = repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=validated["asset_type"],
        project_id=payload.project_id,
        project_id_provided=True,
        notes=_parse_optional_str(payload.notes),
        tags=validated["tags"],
        current_user=user,
        notes_provided=True,
    )
    return {"asset_id": updated.id, "ip_address": updated.ip_address}
