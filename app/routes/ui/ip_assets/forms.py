from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import validate_ip_address
from app.routes.ui.utils import (
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int,
    _parse_optional_str,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

from .helpers import (
    _friendly_audit_changes,
    _ip_asset_form_context,
    _parse_selected_tags,
)

router = APIRouter()


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
        _ip_asset_form_context(
            title="ipocket - Add IP",
            asset_id=None,
            ip_address="",
            asset_type=IPAssetType.VM.value,
            project_id=None,
            host_id=None,
            notes=None,
            tags=[],
            projects=projects,
            hosts=hosts,
            tags_catalog=tags,
            errors=[],
            mode="create",
            action_url="/ui/ip-assets/new",
            submit_label="Create",
        ),
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
            _ip_asset_form_context(
                title="ipocket - Add IP",
                asset_id=None,
                ip_address=ip_address or "",
                asset_type=asset_type or "",
                project_id=project_id,
                host_id=host_id,
                notes=notes,
                tags=tags,
                projects=projects,
                hosts=hosts,
                tags_catalog=tags_catalog,
                errors=errors,
                mode="create",
                action_url="/ui/ip-assets/new",
                submit_label="Create",
            ),
            status_code=400,
            active_nav="ip-assets",
        )

    try:
        repository.create_ip_asset(
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
            _ip_asset_form_context(
                title="ipocket - Add IP",
                asset_id=None,
                ip_address=ip_address or "",
                asset_type=asset_type or "",
                project_id=project_id,
                host_id=host_id,
                notes=notes,
                tags=tags,
                projects=projects,
                hosts=hosts,
                tags_catalog=tags_catalog,
                errors=errors,
                mode="create",
                action_url="/ui/ip-assets/new",
                submit_label="Create",
            ),
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
    view_model = _build_asset_view_models(
        [asset], project_lookup, host_lookup, tag_lookup
    )[0]
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
        {
            "title": "ipocket - IP Detail",
            "asset": view_model,
            "audit_logs": audit_log_rows,
        },
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
        _ip_asset_form_context(
            title="ipocket - Edit IP",
            asset_id=asset.id,
            ip_address=asset.ip_address,
            asset_type=asset.asset_type.value,
            project_id=asset.project_id,
            host_id=asset.host_id,
            notes=asset.notes,
            tags=selected_tags,
            projects=projects,
            hosts=hosts,
            tags_catalog=tags_catalog,
            errors=[],
            mode="edit",
            action_url=f"/ui/ip-assets/{asset.id}/edit",
            submit_label="Save changes",
        ),
        active_nav="ip-assets",
    )


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
            _ip_asset_form_context(
                title="ipocket - Edit IP",
                asset_id=asset.id,
                ip_address=asset.ip_address,
                asset_type=asset_type or "",
                project_id=project_id,
                host_id=host_id,
                notes=notes,
                tags=tags,
                projects=projects,
                hosts=hosts,
                tags_catalog=tags_catalog,
                errors=errors,
                mode="edit",
                action_url=f"/ui/ip-assets/{asset.id}/edit",
                submit_label="Save changes",
            ),
            status_code=400,
            active_nav="ip-assets",
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=normalized_asset_type,
        project_id=project_id,
        project_id_provided=True,
        host_id=host_id,
        host_id_provided=True,
        notes=notes,
        tags=tags,
        current_user=user,
        notes_provided=True,
    )
    if return_to.startswith("/"):
        return RedirectResponse(url=return_to, status_code=303)
    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)
