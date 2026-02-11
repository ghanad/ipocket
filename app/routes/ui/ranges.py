from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import normalize_cidr, normalize_tag_names, split_tag_string, validate_ip_address
from .utils import (
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _collect_inline_ip_errors,
    _normalize_asset_type,
    _parse_form_data,
    _parse_optional_int,
    _parse_optional_str,
    _parse_positive_int_query,
    _render_template,
    _redirect_with_flash,
    require_ui_editor,
)

router = APIRouter()


def _build_range_table_rows(
    ranges: list,
    utilization: list[dict[str, object]],
) -> list[dict[str, object]]:
    utilization_by_id = {
        row.get("id"): row for row in utilization if row.get("id") is not None
    }
    rows: list[dict[str, object]] = []
    for ip_range in ranges:
        summary = utilization_by_id.get(ip_range.id, {})
        rows.append(
            {
                "id": ip_range.id,
                "name": ip_range.name,
                "cidr": ip_range.cidr,
                "notes": ip_range.notes,
                "total_usable": summary.get("total_usable"),
                "used": summary.get("used"),
                "free": summary.get("free"),
                "utilization_percent": summary.get("utilization_percent"),
            }
        )
    return rows

@router.get("/ui/ranges", response_class=HTMLResponse)
def ui_list_ranges(request: Request, connection=Depends(get_connection)) -> HTMLResponse:
    edit_param = request.query_params.get("edit")
    edit_range_id = _parse_optional_int(edit_param)
    edit_ip_range = repository.get_ip_range_by_id(connection, edit_range_id) if edit_range_id else None
    delete_param = request.query_params.get("delete")
    delete_range_id = _parse_optional_int(delete_param)
    delete_ip_range = repository.get_ip_range_by_id(connection, delete_range_id) if delete_range_id else None
    ranges = list(repository.list_ip_ranges(connection))
    utilization = repository.get_ip_range_utilization(connection)
    range_rows = _build_range_table_rows(ranges, utilization)
    return _render_template(
        request,
        "ranges.html",
        {
            "title": "ipocket - IP Ranges",
            "range_rows": range_rows,
            "errors": [],
            "form_state": {"name": "", "cidr": "", "notes": ""},
            "edit_errors": [],
            "edit_form_state": {
                "name": edit_ip_range.name if edit_ip_range else "",
                "cidr": edit_ip_range.cidr if edit_ip_range else "",
                "notes": edit_ip_range.notes if edit_ip_range else "",
            },
            "edit_ip_range": edit_ip_range,
            "delete_errors": [],
            "delete_confirm_value": "",
            "delete_ip_range": delete_ip_range,
        },
        active_nav="ranges",
    )

@router.post("/ui/ranges", response_class=HTMLResponse)
async def ui_create_range(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append("CIDR must be a valid IPv4 network (example: 192.168.10.0/24).")

    if errors:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        range_rows = _build_range_table_rows(ranges, utilization)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": range_rows,
                "errors": errors,
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        repository.create_ip_range(connection, name=name, cidr=normalized_cidr or cidr, notes=notes)
    except sqlite3.IntegrityError:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        range_rows = _build_range_table_rows(ranges, utilization)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": range_rows,
                "errors": ["CIDR already exists."],
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=409,
            active_nav="ranges",
        )

    return RedirectResponse(url="/ui/ranges", status_code=303)

@router.get("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
def ui_edit_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    if repository.get_ip_range_by_id(connection, range_id) is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url=f"/ui/ranges?edit={range_id}", status_code=303)

@router.post("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
async def ui_update_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append("CIDR must be a valid IPv4 network (example: 192.168.10.0/24).")

    if errors:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": errors,
                "edit_form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_ip_range": ip_range,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        updated_range = repository.update_ip_range(
            connection,
            range_id,
            name=name,
            cidr=normalized_cidr or cidr,
            notes=notes,
        )
    except sqlite3.IntegrityError:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": ["CIDR already exists."],
                "edit_form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_ip_range": ip_range,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=409,
            active_nav="ranges",
        )

    if updated_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    return RedirectResponse(url="/ui/ranges", status_code=303)

@router.get("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
def ui_delete_range_confirm(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url=f"/ui/ranges?delete={range_id}", status_code=303)

@router.post("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
async def ui_delete_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    if confirm_name != ip_range.name:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": ["برای حذف کامل، نام رنج را دقیقاً وارد کنید."],
                "delete_confirm_value": confirm_name,
                "delete_ip_range": ip_range,
            },
            status_code=400,
            active_nav="ranges",
        )

    deleted = repository.delete_ip_range(connection, range_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url="/ui/ranges", status_code=303)

@router.get("/ui/ranges/{range_id}/addresses", response_class=HTMLResponse)
def ui_range_addresses(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
) -> HTMLResponse:
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    addresses = breakdown["addresses"]
    display_limit = 512

    return _render_template(
        request,
        "range_addresses.html",
        {
            "title": "ipocket - Range Addresses",
            "ip_range": breakdown["ip_range"],
            "addresses": addresses,
            "used_total": breakdown["used"],
            "free_total": breakdown["free"],
            "total_usable": breakdown["total_usable"],
            "display_limit": display_limit,
            "address_display": addresses[:display_limit],
            "address_overflow": len(addresses) > display_limit,
            "projects": list(repository.list_projects(connection)),
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
        },
        active_nav="ranges",
    )

@router.post("/ui/ranges/{range_id}/addresses/add", response_class=HTMLResponse)
async def ui_range_quick_add_address(
    range_id: int,
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.get("tags") or ""
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

    if project_id is not None and not any(project.id == project_id for project in projects):
        errors.append("Selected project does not exist.")
    try:
        tags = normalize_tag_names(split_tag_string(tags_raw)) if tags_raw else []
    except ValueError as exc:
        tags = []
        errors.append(str(exc))

    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    address_lookup = {
        entry["ip_address"]: entry for entry in breakdown["addresses"]
    }
    if ip_address and ip_address not in address_lookup:
        errors.append("IP address is not part of this range.")
    elif ip_address and address_lookup[ip_address]["status"] != "free":
        errors.append("IP address is already assigned.")

    if errors:
        addresses = breakdown["addresses"]
        display_limit = 512
        return _render_template(
            request,
            "range_addresses.html",
            {
                "title": "ipocket - Range Addresses",
                "ip_range": breakdown["ip_range"],
                "addresses": addresses,
                "used_total": breakdown["used"],
                "free_total": breakdown["free"],
                "total_usable": breakdown["total_usable"],
                "display_limit": display_limit,
                "address_display": addresses[:display_limit],
                "address_overflow": len(addresses) > display_limit,
                "projects": projects,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
            },
            status_code=400,
            active_nav="ranges",
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
        addresses = breakdown["addresses"]
        display_limit = 512
        return _render_template(
            request,
            "range_addresses.html",
            {
                "title": "ipocket - Range Addresses",
                "ip_range": breakdown["ip_range"],
                "addresses": addresses,
                "used_total": breakdown["used"],
                "free_total": breakdown["free"],
                "total_usable": breakdown["total_usable"],
                "display_limit": display_limit,
                "address_display": addresses[:display_limit],
                "address_overflow": len(addresses) > display_limit,
                "projects": projects,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
            },
            status_code=409,
            active_nav="ranges",
        )

    ip_anchor = (ip_address or "").replace(".", "-").replace(":", "-")
    return RedirectResponse(
        url=f"/ui/ranges/{range_id}/addresses#ip-{ip_anchor}",
        status_code=303,
    )

@router.post("/ui/ranges/{range_id}/addresses/{asset_id}/edit", response_class=HTMLResponse)
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

    range_entry = next((entry for entry in breakdown["addresses"] if entry["asset_id"] == asset.id), None)
    if range_entry is None:
        raise HTTPException(status_code=404, detail="IP asset not found in this range.")

    form_data = await _parse_form_data(request)
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.get("tags") or ""
    projects = list(repository.list_projects(connection))

    errors: list[str] = []
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if project_id is not None and not any(project.id == project_id for project in projects):
        errors.append("Selected project does not exist.")
    try:
        tags = normalize_tag_names(split_tag_string(tags_raw)) if tags_raw else []
    except ValueError as exc:
        tags = []
        errors.append(str(exc))

    if errors:
        addresses = breakdown["addresses"]
        display_limit = 512
        return _render_template(
            request,
            "range_addresses.html",
            {
                "title": "ipocket - Range Addresses",
                "ip_range": breakdown["ip_range"],
                "addresses": addresses,
                "used_total": breakdown["used"],
                "free_total": breakdown["free"],
                "total_usable": breakdown["total_usable"],
                "display_limit": display_limit,
                "address_display": addresses[:display_limit],
                "address_overflow": len(addresses) > display_limit,
                "projects": projects,
                "types": [asset_type_item.value for asset_type_item in IPAssetType],
                "errors": errors,
            },
            status_code=400,
            active_nav="ranges",
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=normalized_asset_type,
        project_id=project_id,
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
