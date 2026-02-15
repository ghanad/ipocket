from __future__ import annotations

import sqlite3
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_connection
from app.models import IPAssetType
from app.routes.ui.utils import (
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int,
    _parse_optional_int_query,
    _parse_optional_str,
    _parse_positive_int_query,
    _render_template,
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


def _render_range_addresses(
    request: Request,
    range_id: int,
    connection,
    errors: Optional[list[str]] = None,
    status_code: int = 200,
) -> HTMLResponse:
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    per_page_value = _parse_positive_int_query(
        request.query_params.get("per-page"), _DEFAULT_PAGE_SIZE
    )
    if per_page_value not in _ALLOWED_PAGE_SIZES:
        per_page_value = _DEFAULT_PAGE_SIZE
    page_value = _parse_positive_int_query(request.query_params.get("page"), 1)
    status_filter = _normalize_status_filter(request.query_params.get("status"))
    ip_query_value = (request.query_params.get("q") or "").strip()
    ip_query = ip_query_value.lower()
    project_filter_value = (request.query_params.get("project_id") or "").strip()
    project_unassigned_only = project_filter_value == "unassigned"
    parsed_project_id = (
        None
        if project_unassigned_only
        else _parse_optional_int_query(project_filter_value)
    )
    if (
        project_filter_value
        and not project_unassigned_only
        and parsed_project_id is None
    ):
        project_filter_value = ""
    raw_tag_values = request.query_params.getlist("tag")
    try:
        tag_values = normalize_tag_names(raw_tag_values) if raw_tag_values else []
    except ValueError:
        tag_values = []
    asset_type_filter = None
    try:
        asset_type_filter = _normalize_asset_type(request.query_params.get("type"))
    except ValueError:
        asset_type_filter = None

    addresses = list(breakdown["addresses"])
    if status_filter != "all":
        addresses = [
            entry
            for entry in addresses
            if str(entry.get("status") or "") == status_filter
        ]
    if ip_query:
        addresses = [
            entry
            for entry in addresses
            if ip_query in str(entry.get("ip_address") or "").lower()
        ]
    if project_unassigned_only:
        addresses = [
            entry
            for entry in addresses
            if entry.get("status") == "used" and bool(entry.get("project_unassigned"))
        ]
    elif parsed_project_id is not None:
        addresses = [
            entry
            for entry in addresses
            if entry.get("status") == "used"
            and entry.get("project_id") == parsed_project_id
        ]
    if asset_type_filter is not None:
        addresses = [
            entry
            for entry in addresses
            if entry.get("status") == "used"
            and str(entry.get("asset_type") or "") == asset_type_filter.value
        ]
    if tag_values:
        tag_filter_set = set(tag_values)
        addresses = [
            entry
            for entry in addresses
            if entry.get("status") == "used"
            and any(
                str(tag.get("name", "")).strip().lower() in tag_filter_set
                for tag in (entry.get("tags") or [])
                if isinstance(tag, dict)
            )
        ]

    total_count = len(addresses)
    total_pages = max(1, (total_count + per_page_value - 1) // per_page_value)
    page_value = max(1, min(page_value, total_pages))
    start = (page_value - 1) * per_page_value
    end = start + per_page_value
    paged_addresses = addresses[start:end]

    pagination_params: dict[str, object] = {"per-page": per_page_value}
    if ip_query_value:
        pagination_params["q"] = ip_query_value
    if project_unassigned_only:
        pagination_params["project_id"] = "unassigned"
    elif parsed_project_id is not None:
        pagination_params["project_id"] = parsed_project_id
    if asset_type_filter is not None:
        pagination_params["type"] = asset_type_filter.value
    if tag_values:
        pagination_params["tag"] = tag_values
    if status_filter != "all":
        pagination_params["status"] = status_filter

    base_query = urlencode(pagination_params, doseq=True)
    preserved_query_items: list[tuple[str, str]] = []
    for key, value in pagination_params.items():
        if key == "per-page":
            continue
        if isinstance(value, list):
            preserved_query_items.extend((key, str(item)) for item in value)
            continue
        preserved_query_items.append((key, str(value)))

    is_htmx = request.headers.get("HX-Request") is not None
    template_name = (
        "partials/range_addresses_table.html" if is_htmx else "range_addresses.html"
    )

    context = {
        "title": "ipocket - Range Addresses",
        "ip_range": breakdown["ip_range"],
        "used_total": breakdown["used"],
        "free_total": breakdown["free"],
        "total_usable": breakdown["total_usable"],
        "projects": list(repository.list_projects(connection)),
        "tags": list(repository.list_tags(connection)),
        "types": [asset.value for asset in IPAssetType],
        "errors": errors or [],
        "address_display": paged_addresses,
        "filters": {
            "q": ip_query_value,
            "project_filter": (
                "unassigned"
                if project_unassigned_only
                else str(parsed_project_id or "")
            ),
            "type": asset_type_filter.value if asset_type_filter else "",
            "tag": tag_values,
            "status": status_filter,
        },
        "pagination": {
            "page": page_value,
            "per_page": per_page_value,
            "total": total_count,
            "total_pages": total_pages,
            "has_prev": page_value > 1,
            "has_next": page_value < total_pages,
            "start_index": start + 1 if total_count else 0,
            "end_index": min(page_value * per_page_value, total_count)
            if total_count
            else 0,
            "base_query": base_query,
            "preserved_query_items": preserved_query_items,
        },
    }

    return _render_template(
        request,
        template_name,
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
    projects = list(repository.list_projects(connection))

    errors: list[str] = []
    if not ip_address:
        errors.append("IP address is required.")
    else:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(exc.detail)

    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")

    if project_id is not None and not any(
        project.id == project_id for project in projects
    ):
        errors.append("Selected project does not exist.")
    tags, tag_errors = _parse_selected_tags(connection, tags_raw)
    errors.extend(tag_errors)

    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    address_lookup = {entry["ip_address"]: entry for entry in breakdown["addresses"]}
    if ip_address and ip_address not in address_lookup:
        errors.append("IP address is not part of this range.")
    elif ip_address and address_lookup[ip_address]["status"] != "free":
        errors.append("IP address is already assigned.")

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
            asset_type=normalized_asset_type,
            project_id=project_id,
            notes=notes,
            tags=tags,
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
    projects = list(repository.list_projects(connection))

    errors: list[str] = []
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if project_id is not None and not any(
        project.id == project_id for project in projects
    ):
        errors.append("Selected project does not exist.")
    tags, tag_errors = _parse_selected_tags(connection, tags_raw)
    errors.extend(tag_errors)

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
        asset_type=normalized_asset_type,
        project_id=project_id,
        project_id_provided=True,
        notes=notes,
        tags=tags,
        current_user=user,
        notes_provided=True,
    )

    ip_anchor = asset.ip_address.replace(".", "-").replace(":", "-")
    return RedirectResponse(
        url=f"/ui/ranges/{range_id}/addresses#ip-{ip_anchor}",
        status_code=303,
    )
