from __future__ import annotations

import math
import sqlite3

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import normalize_tag_names, validate_ip_address
from .utils import (
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _collect_inline_ip_errors,
    _parse_form_data,
    _parse_inline_ip_list,
    _parse_optional_int,
    _parse_optional_str,
    _parse_positive_int_query,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

router = APIRouter()

@router.get("/ui/hosts", response_class=HTMLResponse)
def ui_list_hosts(
    request: Request,
    q: Optional[str] = None,
    delete: Optional[int] = Query(default=None),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
) -> HTMLResponse:
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)

    q_value = (q or "").strip()
    if q_value:
        # When searching, filter in Python and paginate the filtered results
        all_hosts = repository.list_hosts_with_ip_counts(connection)
        q_lower = q_value.lower()
        filtered_hosts = [
            host
            for host in all_hosts
            if q_lower in (host["name"] or "").lower()
            or q_lower in (host["notes"] or "").lower()
            or q_lower in (host["vendor"] or "").lower()
            or q_lower in (host["project_name"] or "").lower()
            or q_lower in (host["os_ips"] or "").lower()
            or q_lower in (host["bmc_ips"] or "").lower()
        ]
        total_count = len(filtered_hosts)
        total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
        page_value = max(1, min(page_value, total_pages))
        offset = (page_value - 1) * per_page_value if total_count else 0
        hosts = filtered_hosts[offset:offset + per_page_value]
    else:
        # No search: use paginated query
        total_count = repository.count_hosts(connection)
        total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
        page_value = max(1, min(page_value, total_pages))
        offset = (page_value - 1) * per_page_value if total_count else 0
        hosts = repository.list_hosts_with_ip_counts_paginated(connection, limit=per_page_value, offset=offset)

    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    query_params = {"per-page": per_page_value}
    if q_value:
        query_params["q"] = q_value
    base_query = urlencode(query_params)
    delete_host = repository.get_host_by_id(connection, delete) if delete is not None else None
    if delete is not None and delete_host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    delete_linked_count = 0
    if delete_host is not None:
        linked = repository.get_host_linked_assets_grouped(connection, delete_host.id)
        delete_linked_count = len(linked["os"]) + len(linked["bmc"]) + len(linked["other"])

    return _render_template(
        request,
        "hosts.html",
        {
            "title": "ipocket - Hosts",
            "hosts": hosts,
            "errors": [],
            "vendors": list(repository.list_vendors(connection)),
            "projects": list(repository.list_projects(connection)),
            "form_state": {"name": "", "notes": "", "vendor_id": "", "os_ips": "", "bmc_ips": ""},
            "filters": {"q": q_value},
            "show_search": bool(q_value),
            "show_add_host": False,
            "delete_host": delete_host,
            "delete_errors": [],
            "delete_confirm_value": "",
            "delete_linked_count": delete_linked_count,
            "pagination": {
                "page": page_value,
                "per_page": per_page_value,
                "total": total_count,
                "total_pages": total_pages,
                "has_prev": page_value > 1,
                "has_next": page_value < total_pages,
                "start_index": start_index,
                "end_index": end_index,
                "base_query": base_query,
            },
        },
        active_nav="hosts",
    )

@router.post("/ui/hosts", response_class=HTMLResponse)
async def ui_create_host(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))
    vendor_raw = form_data.get("vendor_id")
    project_raw = form_data.get("project_id")
    vendor_id: Optional[int] = None
    project_id: Optional[int] = None
    errors = []
    try:
        vendor_id = _parse_optional_int(vendor_raw)
    except (TypeError, ValueError):
        errors.append("Select a valid vendor.")
    try:
        project_id = _parse_optional_int(project_raw)
    except (TypeError, ValueError):
        errors.append("Select a valid project.")
    os_ips_raw = form_data.get("os_ips")
    bmc_ips_raw = form_data.get("bmc_ips")
    os_ips = _parse_inline_ip_list(os_ips_raw)
    bmc_ips = _parse_inline_ip_list(bmc_ips_raw)

    projects = list(repository.list_projects(connection))
    if project_id is not None and all(project.id != project_id for project in projects):
        errors.append("Selected project does not exist.")

    if not name:
        errors.append("Host name is required.")
    inline_errors, inline_assets_to_create, inline_assets_to_update = _collect_inline_ip_errors(connection, None, os_ips, bmc_ips)
    errors.extend(inline_errors)

    if errors:
        hosts = repository.list_hosts_with_ip_counts(connection)
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": errors,
                "hosts": hosts,
                "vendors": list(repository.list_vendors(connection)),
                "projects": projects,
                "form_state": {
                    "name": name,
                    "notes": notes or "",
                    "vendor_id": str(vendor_id or ""),
                    "project_id": str(project_id or ""),
                    "os_ips": os_ips_raw or "",
                    "bmc_ips": bmc_ips_raw or "",
                },
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": True,
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        vendor = repository.get_vendor_by_id(connection, vendor_id) if vendor_id is not None else None
        if vendor_id is not None and vendor is None:
            raise sqlite3.IntegrityError("Selected vendor does not exist.")
        host = repository.create_host(connection, name=name, notes=notes, vendor=vendor.name if vendor else None)
        # Create new IP assets
        for ip_address, asset_type in inline_assets_to_create:
            repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                project_id=project_id,
                host_id=host.id,
                notes=None,
                tags=[],
                auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            )
        # Link existing IP assets to the host
        for ip_address, asset_type in inline_assets_to_update:
            update_kwargs: dict[str, object] = {
                "ip_address": ip_address,
                "asset_type": asset_type,
                "host_id": host.id,
            }
            if project_id is not None:
                update_kwargs["project_id"] = project_id
            repository.update_ip_asset(connection, **update_kwargs)
    except sqlite3.IntegrityError:
        hosts = repository.list_hosts_with_ip_counts(connection)
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name already exists."],
                "hosts": hosts,
                "vendors": list(repository.list_vendors(connection)),
                "projects": projects,
                "form_state": {
                    "name": name,
                    "notes": notes or "",
                    "vendor_id": str(vendor_id or ""),
                    "project_id": str(project_id or ""),
                    "os_ips": os_ips_raw or "",
                    "bmc_ips": bmc_ips_raw or "",
                },
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": True,
            },
            status_code=409,
            active_nav="hosts",
        )

    return _redirect_with_flash(
        request,
        "/ui/hosts",
        "Host created.",
        message_type="success",
        status_code=303,
    )

@router.post("/ui/hosts/{host_id}/edit", response_class=HTMLResponse)
async def ui_edit_host(
    host_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))
    vendor_id = _parse_optional_int(form_data.get("vendor_id"))
    os_ips_raw = form_data.get("os_ips")
    bmc_ips_raw = form_data.get("bmc_ips")
    os_ips_provided = os_ips_raw is not None
    bmc_ips_provided = bmc_ips_raw is not None
    project_raw = form_data.get("project_id")
    project_id = _parse_optional_int(project_raw)
    os_ips = _parse_inline_ip_list(os_ips_raw)
    bmc_ips = _parse_inline_ip_list(bmc_ips_raw)

    if not name:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name is required."],
                "toast_messages": [{"type": "error", "message": "Host name is required."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=400,
            active_nav="hosts",
        )

    vendor = repository.get_vendor_by_id(connection, vendor_id) if vendor_id is not None else None
    if vendor_id is not None and vendor is None:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Selected vendor does not exist."],
                "toast_messages": [{"type": "error", "message": "Selected vendor does not exist."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=422,
            active_nav="hosts",
        )

    inline_errors, inline_assets_to_create, inline_assets_to_update = _collect_inline_ip_errors(connection, host_id, os_ips, bmc_ips)
    if inline_errors:
        toast_messages = [{"type": "error", "message": error} for error in inline_errors]
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": inline_errors,
                "toast_messages": toast_messages,
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": "", "os_ips": "", "bmc_ips": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        updated = repository.update_host(
            connection,
            host_id=host_id,
            name=name,
            notes=notes,
            vendor=vendor.name if vendor else None,
        )
        # Keep host OS/BMC links in sync with the edit form:
        # omitted IPs should be unlinked from this host.
        linked = repository.get_host_linked_assets_grouped(connection, host_id)
        current_os_ips = {asset.ip_address for asset in linked["os"]}
        current_bmc_ips = {asset.ip_address for asset in linked["bmc"]}
        removed_os_ips = sorted(current_os_ips - set(os_ips)) if os_ips_provided else []
        removed_bmc_ips = sorted(current_bmc_ips - set(bmc_ips)) if bmc_ips_provided else []
        for removed_ips, asset_type in (
            (removed_os_ips, IPAssetType.OS),
            (removed_bmc_ips, IPAssetType.BMC),
        ):
            if not removed_ips:
                continue
            placeholders = ",".join(["?"] * len(removed_ips))
            connection.execute(
                f"""
                UPDATE ip_assets
                SET host_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE host_id = ?
                  AND type = ?
                  AND ip_address IN ({placeholders})
                """,
                [host_id, asset_type.value, *removed_ips],
            )
        if removed_os_ips or removed_bmc_ips:
            connection.commit()
        set_project_id = project_raw is not None
        if set_project_id:
            projects = repository.list_projects(connection)
            if project_id is not None and all(project.id != project_id for project in projects):
                return _render_template(
                    request,
                    "hosts.html",
                    {
                        "title": "ipocket - Hosts",
                        "errors": ["Selected project does not exist."],
                        "toast_messages": [{"type": "error", "message": "Selected project does not exist."}],
                        "hosts": repository.list_hosts_with_ip_counts(connection),
                        "vendors": list(repository.list_vendors(connection)),
                        "projects": list(projects),
                        "form_state": {"name": "", "notes": "", "vendor_id": ""},
                        "filters": {"q": ""},
                        "show_search": False,
                        "show_add_host": False,
                    },
                    status_code=422,
                    active_nav="hosts",
                )
            linked = repository.get_host_linked_assets_grouped(connection, host_id)
            asset_ids = [asset.id for group in linked.values() for asset in group]
            if asset_ids:
                should_update = any(asset.project_id != project_id for group in linked.values() for asset in group)
                if should_update:
                    repository.bulk_update_ip_assets(
                        connection,
                        asset_ids,
                        project_id=project_id,
                        set_project_id=True,
                    )
        # Create new IP assets
        for ip_address, asset_type in inline_assets_to_create:
            repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host_id,
                notes=None,
                tags=[],
                auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            )
        # Link existing IP assets to the host
        for ip_address, asset_type in inline_assets_to_update:
            repository.update_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host_id,
            )
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name already exists."],
                "toast_messages": [{"type": "error", "message": "Host name already exists."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=409,
            active_nav="hosts",
        )

    if updated is None:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/hosts",
        "Host updated.",
        message_type="success",
        status_code=303,
    )

@router.get("/ui/hosts/{host_id}", response_class=HTMLResponse)
def ui_host_detail(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
) -> HTMLResponse:
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    return _render_template(
        request,
        "host_detail.html",
        {
            "title": "ipocket - Host Detail",
            "host": host,
            "os_assets": grouped["os"],
            "bmc_assets": grouped["bmc"],
            "other_assets": grouped["other"],
        },
        active_nav="hosts",
    )

@router.get("/ui/hosts/{host_id}/delete", response_class=HTMLResponse)
def ui_delete_host_confirm(
    request: Request,
    host_id: int,
    _user=Depends(require_ui_editor),
):
    return _redirect_with_flash(
        request,
        f"/ui/hosts?{urlencode({'delete': host_id})}",
        "",
        status_code=303,
    )

@router.post("/ui/hosts/{host_id}/delete", response_class=HTMLResponse)
async def ui_delete_host(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    linked = repository.get_host_linked_assets_grouped(connection, host_id)
    linked_count = len(linked["os"]) + len(linked["bmc"]) + len(linked["other"])

    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    if confirm_name != host.name:
        hosts = repository.list_hosts_with_ip_counts_paginated(connection, limit=20, offset=0)
        total_count = repository.count_hosts(connection)
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "hosts": hosts,
                "errors": [],
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": "", "os_ips": "", "bmc_ips": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
                "delete_host": host,
                "delete_errors": ["برای حذف کامل، نام Host را دقیقاً وارد کنید."],
                "delete_confirm_value": confirm_name,
                "delete_linked_count": linked_count,
                "pagination": {
                    "page": 1,
                    "per_page": 20,
                    "total": total_count,
                    "total_pages": max(1, math.ceil(total_count / 20)),
                    "has_prev": False,
                    "has_next": total_count > 20,
                    "start_index": 1 if total_count else 0,
                    "end_index": min(20, total_count),
                    "base_query": "per-page=20",
                },
            },
            status_code=400,
            active_nav="hosts",
        )

    deleted = repository.delete_host(connection, host_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return _redirect_with_flash(
        request,
        "/ui/hosts",
        f"Host {host.name} deleted.",
        message_type="success",
        status_code=303,
    )
