from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import validate_ip_address
from app.routes.ui.utils import (
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int,
    _parse_optional_str,
    _render_template,
    require_ui_editor,
)

from . import repository
from .common import _parse_selected_tags

router = APIRouter()


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
            "tags": list(repository.list_tags(connection)),
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
    form_data = await request.form()
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = [str(tag) for tag in form_data.getlist("tags")]
    projects = list(repository.list_projects(connection))
    tags_catalog = list(repository.list_tags(connection))

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
                "tags": tags_catalog,
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
                "tags": tags_catalog,
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
    tags_catalog = list(repository.list_tags(connection))

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
                "tags": tags_catalog,
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
