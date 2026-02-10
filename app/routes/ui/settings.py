
from __future__ import annotations

import math
import sqlite3

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import repository
from app.dependencies import get_connection
from app.utils import DEFAULT_PROJECT_COLOR, DEFAULT_TAG_COLOR, normalize_hex_color, normalize_tag_name
from .utils import (
    _normalize_project_color,
    _parse_form_data,
    _parse_optional_str,
    _parse_positive_int_query,
    _render_template,
    _redirect_with_flash,
    get_current_ui_user,
    require_ui_editor,
)

router = APIRouter()

@router.get("/ui/projects", response_class=HTMLResponse)
def ui_list_projects(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    projects = list(repository.list_projects(connection))
    return _render_template(
        request,
        "projects.html",
        {
            "title": "ipocket - Projects",
            "projects": projects,
            "errors": [],
            "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
        },
        active_nav="projects",
    )

@router.post("/ui/projects/{project_id}/edit", response_class=HTMLResponse)
async def ui_update_project(
    project_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    errors = []
    if not name:
        errors.append("Project name is required.")

    normalized_color = None
    if not errors:
        try:
            normalized_color = _normalize_project_color(color) or DEFAULT_PROJECT_COLOR
        except ValueError:
            errors.append("Project color must be a valid hex color (example: #1a2b3c).")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
            },
            status_code=400,
            active_nav="projects",
        )

    try:
        updated = repository.update_project(
            connection,
            project_id=project_id,
            name=name,
            description=description,
            color=normalized_color,
        )
    except sqlite3.IntegrityError:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": ["Project name already exists."],
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
            },
            status_code=409,
            active_nav="projects",
        )

    if updated is None:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project updated.",
        message_type="success",
        status_code=303,
    )

@router.post("/ui/projects", response_class=HTMLResponse)
async def ui_create_project(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    errors = []
    if not name:
        errors.append("Project name is required.")

    normalized_color = None
    if not errors:
        try:
            normalized_color = _normalize_project_color(color) or DEFAULT_PROJECT_COLOR
        except ValueError:
            errors.append("Project color must be a valid hex color (example: #1a2b3c).")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
            },
            status_code=400,
            active_nav="projects",
        )

    try:
        repository.create_project(connection, name=name, description=description, color=normalized_color)
    except sqlite3.IntegrityError:
        errors.append("Project name already exists.")
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
            },
            status_code=409,
            active_nav="projects",
        )

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project created.",
        message_type="success",
        status_code=303,
    )

@router.get("/ui/tags", response_class=HTMLResponse)
def ui_list_tags(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    tags = list(repository.list_tags(connection))
    return _render_template(
        request,
        "tags.html",
        {
            "title": "ipocket - Tags",
            "tags": tags,
            "errors": [],
            "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
        },
        active_nav="tags",
    )

@router.post("/ui/tags", response_class=HTMLResponse)
async def ui_create_tag(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    errors = []
    normalized_name = ""
    if not name:
        errors.append("Tag name is required.")
    else:
        try:
            normalized_name = normalize_tag_name(name)
        except ValueError as exc:
            errors.append(str(exc))

    normalized_color = None
    if not errors:
        try:
            normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
        except ValueError:
            errors.append("Tag color must be a valid hex color (example: #1a2b3c).")

    if errors:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": errors,
                "form_state": {"name": name, "color": color or DEFAULT_TAG_COLOR},
            },
            status_code=400,
            active_nav="tags",
        )

    try:
        repository.create_tag(connection, name=normalized_name, color=normalized_color)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": ["Tag name already exists."],
                "form_state": {"name": name, "color": color or DEFAULT_TAG_COLOR},
            },
            status_code=409,
            active_nav="tags",
        )

    return RedirectResponse(url="/ui/tags", status_code=303)

@router.post("/ui/tags/{tag_id}/edit", response_class=HTMLResponse)
async def ui_edit_tag(
    tag_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    errors = []
    normalized_name = ""
    if not name:
        errors.append("Tag name is required.")
    else:
        try:
            normalized_name = normalize_tag_name(name)
        except ValueError as exc:
            errors.append(str(exc))

    normalized_color = None
    if not errors:
        try:
            normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
        except ValueError:
            errors.append("Tag color must be a valid hex color (example: #1a2b3c).")

    if errors:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": errors,
                "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
            },
            status_code=400,
            active_nav="tags",
        )

    try:
        updated = repository.update_tag(connection, tag_id, normalized_name, normalized_color)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": ["Tag name already exists."],
                "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
            },
            status_code=409,
            active_nav="tags",
        )

    if updated is None:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/tags", status_code=303)

@router.post("/ui/tags/{tag_id}/delete", response_class=HTMLResponse)
async def ui_delete_tag(
    tag_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    deleted = repository.delete_tag(connection, tag_id)
    if not deleted:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/tags", status_code=303)

@router.get("/ui/vendors", response_class=HTMLResponse)
def ui_list_vendors(request: Request, connection=Depends(get_connection)) -> HTMLResponse:
    vendors = list(repository.list_vendors(connection))
    return _render_template(
        request,
        "vendors.html",
        {
            "title": "ipocket - Vendors",
            "vendors": vendors,
            "errors": [],
            "form_state": {"name": ""},
        },
        active_nav="vendors",
    )

@router.post("/ui/vendors", response_class=HTMLResponse)
async def ui_create_vendor(request: Request, connection=Depends(get_connection), _user=Depends(require_ui_editor)) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    if not name:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name is required."],
                "form_state": {"name": name},
            },
            status_code=400,
            active_nav="vendors",
        )
    try:
        repository.create_vendor(connection, name=name)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name already exists."],
                "form_state": {"name": name},
            },
            status_code=409,
            active_nav="vendors",
        )
    return _redirect_with_flash(
        request,
        "/ui/vendors",
        "Vendor created.",
        message_type="success",
        status_code=303,
    )

@router.post("/ui/vendors/{vendor_id}/edit", response_class=HTMLResponse)
async def ui_edit_vendor(vendor_id: int, request: Request, connection=Depends(get_connection), _user=Depends(require_ui_editor)) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    if not name:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name is required."],
                "form_state": {"name": ""},
            },
            status_code=400,
            active_nav="vendors",
        )
    try:
        updated = repository.update_vendor(connection, vendor_id, name)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name already exists."],
                "form_state": {"name": ""},
            },
            status_code=409,
            active_nav="vendors",
        )
    if updated is None:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/vendors", status_code=303)

@router.get("/ui/audit-log", response_class=HTMLResponse)
def ui_audit_log(
    request: Request,
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    total_count = repository.count_audit_logs(connection)
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    audit_logs = repository.list_audit_logs_paginated(
        connection,
        limit=per_page_value,
        offset=offset,
    )
    audit_log_rows = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": log.changes or "",
            "target_label": log.target_label,
        }
        for log in audit_logs
    ]
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    base_query = urlencode({"per-page": per_page_value})
    return _render_template(
        request,
        "audit_log_list.html",
        {
            "title": "ipocket - Audit Log",
            "audit_logs": audit_log_rows,
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
        active_nav="audit-log",
    )
