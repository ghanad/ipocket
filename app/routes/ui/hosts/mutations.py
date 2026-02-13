from __future__ import annotations

import math
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.routes.ui.utils import (
    _collect_inline_ip_errors,
    _is_auto_host_for_bmc_enabled,
    _parse_form_data,
    _parse_inline_ip_list,
    _parse_optional_int,
    _parse_optional_str,
    _redirect_with_flash,
    _render_template,
    require_ui_editor,
)

from .common import empty_host_form_state

router = APIRouter()


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
    inline_errors, inline_assets_to_create, inline_assets_to_update = (
        _collect_inline_ip_errors(connection, None, os_ips, bmc_ips)
    )
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
        vendor = (
            repository.get_vendor_by_id(connection, vendor_id)
            if vendor_id is not None
            else None
        )
        if vendor_id is not None and vendor is None:
            raise sqlite3.IntegrityError("Selected vendor does not exist.")
        host = repository.create_host(
            connection, name=name, notes=notes, vendor=vendor.name if vendor else None
        )
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
                "toast_messages": [
                    {"type": "error", "message": "Host name is required."}
                ],
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

    vendor = (
        repository.get_vendor_by_id(connection, vendor_id)
        if vendor_id is not None
        else None
    )
    if vendor_id is not None and vendor is None:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Selected vendor does not exist."],
                "toast_messages": [
                    {"type": "error", "message": "Selected vendor does not exist."}
                ],
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

    inline_errors, inline_assets_to_create, inline_assets_to_update = (
        _collect_inline_ip_errors(connection, host_id, os_ips, bmc_ips)
    )
    if inline_errors:
        toast_messages = [
            {"type": "error", "message": error} for error in inline_errors
        ]
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
                "form_state": empty_host_form_state(),
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
        linked = repository.get_host_linked_assets_grouped(connection, host_id)
        current_os_ips = {asset.ip_address for asset in linked["os"]}
        current_bmc_ips = {asset.ip_address for asset in linked["bmc"]}
        removed_os_ips = sorted(current_os_ips - set(os_ips)) if os_ips_provided else []
        removed_bmc_ips = (
            sorted(current_bmc_ips - set(bmc_ips)) if bmc_ips_provided else []
        )
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
            if project_id is not None and all(
                project.id != project_id for project in projects
            ):
                return _render_template(
                    request,
                    "hosts.html",
                    {
                        "title": "ipocket - Hosts",
                        "errors": ["Selected project does not exist."],
                        "toast_messages": [
                            {
                                "type": "error",
                                "message": "Selected project does not exist.",
                            }
                        ],
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
                should_update = any(
                    asset.project_id != project_id
                    for group in linked.values()
                    for asset in group
                )
                if should_update:
                    repository.bulk_update_ip_assets(
                        connection,
                        asset_ids,
                        project_id=project_id,
                        set_project_id=True,
                    )
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
                "toast_messages": [
                    {"type": "error", "message": "Host name already exists."}
                ],
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
        hosts = repository.list_hosts_with_ip_counts_paginated(
            connection, limit=20, offset=0
        )
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
                "form_state": empty_host_form_state(),
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
