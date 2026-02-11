from __future__ import annotations

import math
import sqlite3
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import normalize_tag_names, validate_ip_address
from .utils import (
    _append_query_param,
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int,
    _parse_optional_int_query,
    _parse_optional_str,
    _parse_positive_int_query,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

router = APIRouter()

_HIGH_RISK_DELETE_TAGS = {"prod", "production", "critical", "flagged"}


def _friendly_audit_changes(changes: str) -> dict[str, str]:
    normalized = (changes or "").strip()
    if not normalized:
        return {"summary": "No additional details.", "raw": ""}

    if normalized.startswith("Created IP asset "):
        raw_payload = normalized.removeprefix("Created IP asset ").strip()
        compact_payload = raw_payload.strip("()")
        raw_map: dict[str, str] = {}
        for chunk in compact_payload.split(","):
            key, _, value = chunk.strip().partition("=")
            if key:
                raw_map[key.strip()] = value.strip()
        summary_parts = [
            f"Type: {raw_map.get('type', 'Unknown')}",
            (
                "Project: Unassigned"
                if raw_map.get("project_id") in {None, "", "None"}
                else f"Project ID: {raw_map.get('project_id')}"
            ),
            (
                "Host: Unassigned"
                if raw_map.get("host_id") in {None, "", "None"}
                else f"Host ID: {raw_map.get('host_id')}"
            ),
            f"Notes: {(raw_map.get('notes') or 'No notes').strip() or 'No notes'}",
        ]
        return {"summary": "; ".join(summary_parts), "raw": normalized}

    return {"summary": normalized, "raw": normalized}


def _delete_requires_exact_ip(asset, tag_names: list[str]) -> bool:
    normalized_tags = {tag.lower() for tag in tag_names}
    return bool(
        asset.project_id
        or asset.host_id
        or asset.asset_type == IPAssetType.VIP
        or normalized_tags.intersection(_HIGH_RISK_DELETE_TAGS)
    )


def _parse_selected_tags(connection, raw_tags: list[str]) -> tuple[list[str], list[str]]:
    cleaned_tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    try:
        selected_tags = normalize_tag_names(cleaned_tags) if cleaned_tags else []
    except ValueError as exc:
        return [], [str(exc)]
    existing_tags = {tag.name for tag in repository.list_tags(connection)}
    missing_tags = [tag for tag in selected_tags if tag not in existing_tags]
    if missing_tags:
        return [], [f"Selected tags do not exist: {', '.join(missing_tags)}."]
    return selected_tags, []

@router.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    tag: Optional[list[str]] = Query(default=None),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    archived_only: bool = Query(default=False, alias="archived-only"),
    bulk_error: Optional[str] = Query(default=None, alias="bulk-error"),
    bulk_success: Optional[str] = Query(default=None, alias="bulk-success"),
    delete_error: Optional[str] = Query(default=None, alias="delete-error"),
    delete_success: Optional[str] = Query(default=None, alias="delete-success"),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    parsed_project_id = _parse_optional_int_query(project_id)
    try:
        asset_type_enum = _normalize_asset_type(asset_type)
    except ValueError:
        asset_type_enum = None
    q_value = (q or "").strip()
    query_text = q_value or None
    raw_tag_values = tag or []
    try:
        tag_values = normalize_tag_names(raw_tag_values) if raw_tag_values else []
    except ValueError:
        tag_values = []
    total_count = repository.count_active_ip_assets(
        connection,
        project_id=parsed_project_id,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        archived_only=archived_only,
    )
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    assets = repository.list_active_ip_assets_paginated(
        connection,
        project_id=parsed_project_id,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        limit=per_page_value,
        offset=offset,
        archived_only=archived_only,
    )

    projects = list(repository.list_projects(connection))
    tags = list(repository.list_tags(connection))
    project_lookup = {project.id: {"name": project.name, "color": project.color} for project in projects}
    hosts = list(repository.list_hosts(connection))
    host_lookup = {host.id: host.name for host in hosts}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id for asset in assets])
    host_pair_lookup = repository.list_host_pair_ips_for_hosts(
        connection,
        [asset.host_id for asset in assets if asset.host_id],
    )
    view_models = _build_asset_view_models(
        assets,
        project_lookup,
        host_lookup,
        tag_lookup,
        host_pair_lookup,
    )

    is_htmx = request.headers.get("HX-Request") is not None
    template_name = "partials/ip_assets_table.html" if is_htmx else "ip_assets_list.html"
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    pagination_params: dict[str, object] = {"per-page": per_page_value}
    if q_value:
        pagination_params["q"] = q_value
    if parsed_project_id is not None:
        pagination_params["project_id"] = parsed_project_id
    if tag_values:
        pagination_params["tag"] = tag_values
    if asset_type_enum:
        pagination_params["type"] = asset_type_enum.value
    if unassigned_only:
        pagination_params["unassigned-only"] = "true"
    if archived_only:
        pagination_params["archived-only"] = "true"
    base_query = urlencode(pagination_params, doseq=True)
    return_to = request.url.path
    if request.url.query:
        return_to = f"{return_to}?{request.url.query}"
    toast_messages: list[dict[str, str]] = []
    if bulk_error:
        toast_messages.append({"type": "error", "message": bulk_error})
    if bulk_success:
        toast_messages.append({"type": "success", "message": bulk_success})
    if delete_error:
        toast_messages.append({"type": "error", "message": delete_error})
    if delete_success:
        toast_messages.append({"type": "success", "message": delete_success})
    context = {
        "title": "ipocket - IP Assets",
        "assets": view_models,
        "projects": projects,
        "tags": tags,
        "hosts": hosts,
        "types": [asset.value for asset in IPAssetType],
        "return_to": return_to,
        "toast_messages": toast_messages,
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
    }
    if not is_htmx:
        context.update(
            {
                "filters": {
                    "q": q or "",
                    "project_id": parsed_project_id,
                    "tag": tag_values,
                    "type": asset_type_enum.value if asset_type_enum else "",
                    "unassigned_only": unassigned_only,
                    "archived_only": archived_only,
                    "page": page_value,
                    "per_page": per_page_value,
                },
            }
        )

    return _render_template(
        request,
        template_name,
        context,
        active_nav="ip-assets",
    )

@router.post("/ui/ip-assets/bulk-edit", response_class=HTMLResponse)
async def ui_bulk_edit_ip_assets(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    form = await request.form()
    asset_ids_raw = form.getlist("asset_ids")
    return_to = form.get("return_to") or "/ui/ip-assets"
    errors: list[str] = []
    asset_ids: list[int] = []
    for asset_id in asset_ids_raw:
        try:
            asset_ids.append(int(asset_id))
        except (TypeError, ValueError):
            errors.append("Select valid IP assets.")
            break
    if not asset_ids:
        errors.append("Select at least one IP asset.")

    asset_type_raw = (form.get("type") or "").strip()
    asset_type_enum: Optional[IPAssetType] = None
    if asset_type_raw:
        try:
            asset_type_enum = _normalize_asset_type(asset_type_raw)
        except ValueError:
            errors.append("Select a valid type.")

    project_selection = (form.get("project_id") or "").strip()
    set_project_id = False
    project_id_value: Optional[int] = None
    if project_selection:
        set_project_id = True
        if project_selection == "unassigned":
            project_id_value = None
        else:
            project_id_value = _parse_optional_int(project_selection)
            if project_id_value is None:
                errors.append("Select a valid project.")
            elif repository.get_project_by_id(connection, project_id_value) is None:
                errors.append("Selected project does not exist.")

    tags_to_add_raw = [str(tag) for tag in form.getlist("tags")]
    tags_to_add, tag_errors = _parse_selected_tags(connection, tags_to_add_raw)
    errors.extend(tag_errors)

    if not asset_type_enum and not set_project_id and not tags_to_add:
        errors.append("Choose at least one bulk update action.")

    if errors:
        message = errors[0]
        return RedirectResponse(
            url=_append_query_param(return_to, "bulk-error", message),
            status_code=303,
        )

    updated_assets = repository.bulk_update_ip_assets(
        connection,
        asset_ids,
        asset_type=asset_type_enum,
        project_id=project_id_value,
        set_project_id=set_project_id,
        tags_to_add=tags_to_add,
        current_user=user,
    )
    success_message = f"Updated {len(updated_assets)} IP assets."
    return RedirectResponse(
        url=_append_query_param(return_to, "bulk-success", success_message),
        status_code=303,
    )

@router.get("/ui/ip-assets/new", response_class=HTMLResponse)
def ui_add_ip_form(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    tags = list(repository.list_tags(connection))
    return _render_template(
        request,
        "ip_asset_form.html",
        {
            "title": "ipocket - Add IP",
            "asset": {
                "id": None,
                "ip_address": "",
                "type": IPAssetType.VM.value,
                "project_id": "",
                "host_id": "",
                "notes": "",
                "tags": [],
            },
            "projects": projects,
            "hosts": hosts,
            "tags": tags,
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
            "mode": "create",
            "action_url": "/ui/ip-assets/new",
            "submit_label": "Create",
        },
        active_nav="ip-assets",
    )

@router.post("/ui/ip-assets/new", response_class=HTMLResponse)
async def ui_add_ip_submit(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    form_data = await request.form()
    return_to = (str(form_data.get("return_to") or "")).strip()
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.getlist("tags")

    errors = []
    if not ip_address:
        errors.append("IP address is required.")
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if host_id is not None and repository.get_host_by_id(connection, host_id) is None:
        errors.append("Selected host does not exist.")

    if ip_address:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(exc.detail)
    tags, tag_errors = _parse_selected_tags(connection, [str(tag) for tag in tags_raw])
    errors.extend(tag_errors)

    if errors:
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        tags_catalog = list(repository.list_tags(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Add IP",
                "asset": {
                    "id": None,
                    "ip_address": ip_address or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags,
                },
                "projects": projects,
                "hosts": hosts,
                "tags": tags_catalog,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "create",
                "action_url": "/ui/ip-assets/new",
                "submit_label": "Create",
            },
            status_code=400,
            active_nav="ip-assets",
        )

    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=normalized_asset_type,
            project_id=project_id,
            host_id=host_id,
            notes=notes,
            tags=tags,
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError:
        errors.append("IP address already exists.")
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        tags_catalog = list(repository.list_tags(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Add IP",
                "asset": {
                    "id": None,
                    "ip_address": ip_address or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags,
                },
                "projects": projects,
                "hosts": hosts,
                "tags": tags_catalog,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "create",
                "action_url": "/ui/ip-assets/new",
                "submit_label": "Create",
            },
            status_code=409,
            active_nav="ip-assets",
        )

    redirect_target = return_to if return_to.startswith("/") else "/ui/ip-assets"
    return _redirect_with_flash(
        request,
        redirect_target,
        "IP asset created.",
        message_type="success",
        status_code=303,
    )

@router.get("/ui/ip-assets/{asset_id}", response_class=HTMLResponse)
def ui_ip_asset_detail(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in repository.list_projects(connection)
    }
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id])
    view_model = _build_asset_view_models([asset], project_lookup, host_lookup, tag_lookup)[0]
    audit_logs = repository.get_audit_logs_for_ip(connection, asset.id)
    audit_log_rows = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": _friendly_audit_changes(log.changes or ""),
        }
        for log in audit_logs
    ]
    return _render_template(
        request,
        "ip_asset_detail.html",
        {"title": "ipocket - IP Detail", "asset": view_model, "audit_logs": audit_log_rows},
        active_nav="ip-assets",
    )

@router.get("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
def ui_edit_ip_form(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    tags_catalog = list(repository.list_tags(connection))
    tag_lookup = repository.list_tags_for_ip_assets(connection, [asset.id])
    selected_tags = tag_lookup.get(asset.id, [])
    return _render_template(
        request,
        "ip_asset_form.html",
        {
            "title": "ipocket - Edit IP",
            "asset": {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "type": asset.asset_type.value,
                "project_id": asset.project_id or "",
                "host_id": asset.host_id or "",
                "notes": asset.notes or "",
                "tags": selected_tags,
            },
            "projects": projects,
            "hosts": hosts,
            "tags": tags_catalog,
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
            "mode": "edit",
            "action_url": f"/ui/ip-assets/{asset.id}/edit",
            "submit_label": "Save changes",
        },
        active_nav="ip-assets",
    )

@router.post("/ui/ip-assets/{asset_id}/auto-host", response_class=JSONResponse)
def ui_create_auto_host(
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> JSONResponse:
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if asset.asset_type != IPAssetType.BMC:
        return JSONResponse({"error": "Auto-host creation is only available for BMC assets."}, status_code=400)
    if asset.host_id is not None:
        return JSONResponse({"error": "This IP is already assigned to a host."}, status_code=409)

    host_name = f"server_{asset.ip_address}"
    host = repository.get_host_by_name(connection, host_name)
    if host is None:
        host = repository.create_host(connection, name=host_name, notes=None, vendor=None)

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        host_id=host.id,
        current_user=user,
    )

    return JSONResponse({"host_id": host.id, "host_name": host.name})

@router.post("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
async def ui_edit_ip_submit(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form_data = await request.form()
    return_to = (str(form_data.get("return_to") or "")).strip()
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.getlist("tags")

    errors = []
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if host_id is not None and repository.get_host_by_id(connection, host_id) is None:
        errors.append("Selected host does not exist.")
    tags, tag_errors = _parse_selected_tags(connection, [str(tag) for tag in tags_raw])
    errors.extend(tag_errors)

    if errors:
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        tags_catalog = list(repository.list_tags(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Edit IP",
                "asset": {
                    "id": asset.id,
                    "ip_address": asset.ip_address,
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags,
                },
                "projects": projects,
                "hosts": hosts,
                "tags": tags_catalog,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "edit",
                "action_url": f"/ui/ip-assets/{asset.id}/edit",
                "submit_label": "Save changes",
            },
            status_code=400,
            active_nav="ip-assets",
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=normalized_asset_type,
        project_id=project_id,
        host_id=host_id,
        notes=notes,
        tags=tags,
        current_user=user,
        notes_provided=True,
    )
    if return_to.startswith("/"):
        return RedirectResponse(url=return_to, status_code=303)
    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)

@router.get("/ui/ip-assets/{asset_id}/delete", response_class=HTMLResponse)
def ui_delete_ip_asset_confirm(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _render_template(
        request,
        "ip_asset_delete_confirm.html",
        {
            "title": "ipocket - Confirm IP Delete",
            "asset": asset,
            "errors": [],
            "confirm_value": "",
        },
        active_nav="ip-assets",
    )

@router.post("/ui/ip-assets/{asset_id}/delete", response_class=HTMLResponse)
async def ui_delete_ip_asset(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form_data = await request.form()
    return_to = str(form_data.get("return_to") or "/ui/ip-assets").strip()
    confirmation_ack_raw = str(form_data.get("confirm_delete_ack") or "").strip().lower()
    confirmation_ack = bool(confirmation_ack_raw and confirmation_ack_raw not in {"0", "false", "off", "no"})
    confirm_ip = str(form_data.get("confirm_ip") or "").strip()
    tags_map = repository.list_tags_for_ip_assets(connection, [asset.id])
    tag_names = tags_map.get(asset.id, [])
    requires_exact_ip = _delete_requires_exact_ip(asset, tag_names)

    errors: list[str] = []
    if not confirmation_ack:
        errors.append("Confirm that this delete cannot be undone.")
    if requires_exact_ip and confirm_ip != asset.ip_address:
        errors.append("Type the exact IP address to delete this high-risk asset.")

    wants_json = "application/json" in (request.headers.get("accept") or "")
    if errors:
        if wants_json:
            return JSONResponse({"error": errors[0]}, status_code=400)
        return RedirectResponse(
            url=_append_query_param(return_to if return_to.startswith("/") else "/ui/ip-assets", "delete-error", errors[0]),
            status_code=303,
        )

    repository.delete_ip_asset(connection, asset.ip_address, current_user=user)
    if wants_json:
        return JSONResponse(
            {"message": f"Deleted {asset.ip_address}.", "asset_id": asset.id, "ip_address": asset.ip_address}
        )
    success_url = _append_query_param(return_to if return_to.startswith("/") else "/ui/ip-assets", "delete-success", f"Deleted {asset.ip_address}.")
    return RedirectResponse(url=success_url, status_code=303)

@router.post("/ui/ip-assets/{asset_id}/archive")
def ui_archive_ip_asset(
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    repository.archive_ip_asset(connection, asset.ip_address)
    return RedirectResponse(url="/ui/ip-assets", status_code=303)
