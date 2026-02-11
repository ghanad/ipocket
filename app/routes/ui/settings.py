
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
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    connection=Depends(get_connection),
) -> HTMLResponse:
    projects = list(repository.list_projects(connection))
    edit_project = None
    delete_project = None
    if edit is not None:
        edit_project = repository.get_project_by_id(connection, edit)
        if edit_project is None:
            raise HTTPException(status_code=404, detail="Project not found")
    if delete is not None:
        delete_project = repository.get_project_by_id(connection, delete)
        if delete_project is None:
            raise HTTPException(status_code=404, detail="Project not found")

    return _render_template(
        request,
        "projects.html",
        {
            "title": "ipocket - Projects",
            "projects": projects,
            "project_ip_counts": repository.list_project_ip_counts(connection),
            "errors": [],
            "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
            "edit_errors": [],
            "edit_project": edit_project,
            "edit_form_state": {
                "name": edit_project.name if edit_project else "",
                "description": edit_project.description if edit_project and edit_project.description else "",
                "color": edit_project.color if edit_project else DEFAULT_PROJECT_COLOR,
            },
            "delete_errors": [],
            "delete_project": delete_project,
            "delete_confirm_value": "",
        },
        active_nav="projects",
    )


@router.get("/ui/projects/{project_id}/edit", response_class=HTMLResponse)
def ui_open_project_edit(
    project_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/projects?{urlencode({'edit': project_id})}",
        "",
        status_code=303,
    )


@router.get("/ui/projects/{project_id}/delete", response_class=HTMLResponse)
def ui_open_project_delete(
    project_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/projects?{urlencode({'delete': project_id})}",
        "",
        status_code=303,
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
        edit_project = repository.get_project_by_id(connection, project_id)
        if edit_project is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "edit_errors": errors,
                "edit_project": edit_project,
                "edit_form_state": {
                    "name": name,
                    "description": description or "",
                    "color": color or DEFAULT_PROJECT_COLOR,
                },
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
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
        edit_project = repository.get_project_by_id(connection, project_id)
        if edit_project is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "edit_errors": ["Project name already exists."],
                "edit_project": edit_project,
                "edit_form_state": {
                    "name": name,
                    "description": description or "",
                    "color": color or DEFAULT_PROJECT_COLOR,
                },
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
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


@router.post("/ui/projects/{project_id}/delete", response_class=HTMLResponse)
async def ui_delete_project(
    project_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()

    project = repository.get_project_by_id(connection, project_id)
    if project is None:
        return Response(status_code=404)

    if confirm_name != project.name:
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": list(repository.list_projects(connection)),
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "delete_errors": ["Project name confirmation does not match."],
                "delete_project": project,
                "delete_confirm_value": confirm_name,
            },
            status_code=400,
            active_nav="projects",
        )

    deleted = repository.delete_project(connection, project_id)
    if not deleted:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project deleted.",
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
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
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
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
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
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    connection=Depends(get_connection),
) -> HTMLResponse:
    edit_tag = None
    delete_tag = None
    if edit is not None:
        edit_tag = repository.get_tag_by_id(connection, edit)
        if edit_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
    if delete is not None:
        delete_tag = repository.get_tag_by_id(connection, delete)
        if delete_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")

    return _render_template(
        request,
        "tags.html",
        _tags_template_context(connection, edit_tag=edit_tag, delete_tag=delete_tag),
        active_nav="tags",
    )


@router.get("/ui/tags/{tag_id}/edit", response_class=HTMLResponse)
def ui_open_tag_edit(
    tag_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/tags?{urlencode({'edit': tag_id})}",
        "",
        status_code=303,
    )


@router.get("/ui/tags/{tag_id}/delete", response_class=HTMLResponse)
def ui_open_tag_delete(
    tag_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/tags?{urlencode({'delete': tag_id})}",
        "",
        status_code=303,
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
            _tags_template_context(
                connection,
                errors=errors,
                form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=400,
            active_nav="tags",
        )

    try:
        repository.create_tag(connection, name=normalized_name, color=normalized_color)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "tags.html",
            _tags_template_context(
                connection,
                errors=["Tag name already exists."],
                form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=409,
            active_nav="tags",
        )

    return _redirect_with_flash(
        request,
        "/ui/tags",
        "Tag created.",
        message_type="success",
        status_code=303,
    )

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
        edit_tag = repository.get_tag_by_id(connection, tag_id)
        if edit_tag is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "tags.html",
            _tags_template_context(
                connection,
                edit_errors=errors,
                edit_tag=edit_tag,
                edit_form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=400,
            active_nav="tags",
        )

    try:
        updated = repository.update_tag(connection, tag_id, normalized_name, normalized_color)
    except sqlite3.IntegrityError:
        edit_tag = repository.get_tag_by_id(connection, tag_id)
        if edit_tag is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "tags.html",
            _tags_template_context(
                connection,
                edit_errors=["Tag name already exists."],
                edit_tag=edit_tag,
                edit_form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=409,
            active_nav="tags",
        )

    if updated is None:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/tags",
        "Tag updated.",
        message_type="success",
        status_code=303,
    )

@router.post("/ui/tags/{tag_id}/delete", response_class=HTMLResponse)
async def ui_delete_tag(
    tag_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()

    tag = repository.get_tag_by_id(connection, tag_id)
    if tag is None:
        return Response(status_code=404)

    if confirm_name != tag.name:
        return _render_template(
            request,
            "tags.html",
            _tags_template_context(
                connection,
                delete_errors=["Tag name confirmation does not match."],
                delete_tag=tag,
                delete_confirm_value=confirm_name,
            ),
            status_code=400,
            active_nav="tags",
        )

    deleted = repository.delete_tag(connection, tag_id)
    if not deleted:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/tags",
        "Tag deleted.",
        message_type="success",
        status_code=303,
    )


def _tags_template_context(
    connection,
    *,
    errors: Optional[list[str]] = None,
    form_state: Optional[dict[str, str]] = None,
    edit_errors: Optional[list[str]] = None,
    edit_tag=None,
    edit_form_state: Optional[dict[str, str]] = None,
    delete_errors: Optional[list[str]] = None,
    delete_tag=None,
    delete_confirm_value: str = "",
) -> dict:
    return {
        "title": "ipocket - Tags",
        "tags": list(repository.list_tags(connection)),
        "tag_ip_counts": repository.list_tag_ip_counts(connection),
        "errors": errors or [],
        "form_state": form_state or {"name": "", "color": DEFAULT_TAG_COLOR},
        "edit_errors": edit_errors or [],
        "edit_tag": edit_tag,
        "edit_form_state": edit_form_state
        or {
            "name": edit_tag.name if edit_tag else "",
            "color": edit_tag.color if edit_tag else DEFAULT_TAG_COLOR,
        },
        "delete_errors": delete_errors or [],
        "delete_tag": delete_tag,
        "delete_confirm_value": delete_confirm_value,
    }

@router.get("/ui/vendors", response_class=HTMLResponse)
def ui_list_vendors(
    request: Request,
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    connection=Depends(get_connection),
) -> HTMLResponse:
    edit_vendor = None
    delete_vendor = None
    if edit is not None:
        edit_vendor = repository.get_vendor_by_id(connection, edit)
        if edit_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")
    if delete is not None:
        delete_vendor = repository.get_vendor_by_id(connection, delete)
        if delete_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_template(
        request,
        "vendors.html",
        _vendors_template_context(connection, edit_vendor=edit_vendor, delete_vendor=delete_vendor),
        active_nav="vendors",
    )


def _vendors_template_context(
    connection,
    *,
    errors: Optional[list[str]] = None,
    form_state: Optional[dict[str, str]] = None,
    edit_errors: Optional[list[str]] = None,
    edit_vendor=None,
    edit_form_state: Optional[dict[str, str]] = None,
    delete_errors: Optional[list[str]] = None,
    delete_vendor=None,
    delete_confirm_value: str = "",
) -> dict:
    return {
        "title": "ipocket - Vendors",
        "vendors": list(repository.list_vendors(connection)),
        "errors": errors or [],
        "form_state": form_state or {"name": ""},
        "edit_errors": edit_errors or [],
        "edit_vendor": edit_vendor,
        "edit_form_state": edit_form_state or {"name": edit_vendor.name if edit_vendor else ""},
        "delete_errors": delete_errors or [],
        "delete_vendor": delete_vendor,
        "delete_confirm_value": delete_confirm_value,
    }


@router.get("/ui/vendors/{vendor_id}/edit", response_class=HTMLResponse)
def ui_open_vendor_edit(
    vendor_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/vendors?{urlencode({'edit': vendor_id})}",
        "",
        status_code=303,
    )


@router.get("/ui/vendors/{vendor_id}/delete", response_class=HTMLResponse)
def ui_open_vendor_delete(
    vendor_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/vendors?{urlencode({'delete': vendor_id})}",
        "",
        status_code=303,
    )

@router.post("/ui/vendors", response_class=HTMLResponse)
async def ui_create_vendor(
    request: Request,
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()

    edit_vendor = repository.get_vendor_by_id(connection, edit) if edit is not None else None
    delete_vendor = repository.get_vendor_by_id(connection, delete) if delete is not None else None

    if not name:
        return _render_template(
            request,
            "vendors.html",
            _vendors_template_context(
                connection,
                errors=["Vendor name is required."],
                form_state={"name": name},
                edit_vendor=edit_vendor,
                delete_vendor=delete_vendor,
            ),
            status_code=400,
            active_nav="vendors",
        )
    try:
        repository.create_vendor(connection, name=name)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "vendors.html",
            _vendors_template_context(
                connection,
                errors=["Vendor name already exists."],
                form_state={"name": name},
                edit_vendor=edit_vendor,
                delete_vendor=delete_vendor,
            ),
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
        edit_vendor = repository.get_vendor_by_id(connection, vendor_id)
        if edit_vendor is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "vendors.html",
            _vendors_template_context(
                connection,
                edit_errors=["Vendor name is required."],
                edit_vendor=edit_vendor,
                edit_form_state={"name": name},
            ),
            status_code=400,
            active_nav="vendors",
        )
    try:
        updated = repository.update_vendor(connection, vendor_id, name)
    except sqlite3.IntegrityError:
        edit_vendor = repository.get_vendor_by_id(connection, vendor_id)
        if edit_vendor is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "vendors.html",
            _vendors_template_context(
                connection,
                edit_errors=["Vendor name already exists."],
                edit_vendor=edit_vendor,
                edit_form_state={"name": name},
            ),
            status_code=409,
            active_nav="vendors",
        )
    if updated is None:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/vendors",
        "Vendor updated.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/vendors/{vendor_id}/delete", response_class=HTMLResponse)
async def ui_delete_vendor(
    vendor_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    vendor = repository.get_vendor_by_id(connection, vendor_id)
    if vendor is None:
        return Response(status_code=404)

    if confirm_name != vendor.name:
        return _render_template(
            request,
            "vendors.html",
            _vendors_template_context(
                connection,
                delete_errors=["Vendor name confirmation does not match."],
                delete_vendor=vendor,
                delete_confirm_value=confirm_name,
            ),
            status_code=400,
            active_nav="vendors",
        )

    deleted = repository.delete_vendor(connection, vendor_id)
    if not deleted:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/vendors",
        "Vendor deleted.",
        message_type="success",
        status_code=303,
    )

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
