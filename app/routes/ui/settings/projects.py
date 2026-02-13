from __future__ import annotations

import sqlite3
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.dependencies import get_connection
from app.utils import DEFAULT_PROJECT_COLOR
from app.routes.ui.utils import (
    _normalize_project_color,
    _parse_form_data,
    _parse_optional_str,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

from . import repository
from .common import _tags_template_context, _vendors_template_context

router = APIRouter()


@router.get("/ui/projects", response_class=HTMLResponse)
def ui_list_projects(
    request: Request,
    tab: Optional[str] = Query(default=None),
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    connection=Depends(get_connection),
) -> HTMLResponse:
    if tab == "tags":
        edit_tag = (
            repository.get_tag_by_id(connection, edit) if edit is not None else None
        )
        delete_tag = (
            repository.get_tag_by_id(connection, delete) if delete is not None else None
        )
        if edit is not None and edit_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        if delete is not None and delete_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                connection, edit_tag=edit_tag, delete_tag=delete_tag
            ),
            active_nav="library",
        )

    if tab == "vendors":
        edit_vendor = (
            repository.get_vendor_by_id(connection, edit) if edit is not None else None
        )
        delete_vendor = (
            repository.get_vendor_by_id(connection, delete)
            if delete is not None
            else None
        )
        if edit is not None and edit_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if delete is not None and delete_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                connection, edit_vendor=edit_vendor, delete_vendor=delete_vendor
            ),
            active_nav="library",
        )

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
            "form_state": {
                "name": "",
                "description": "",
                "color": DEFAULT_PROJECT_COLOR,
            },
            "edit_errors": [],
            "edit_project": edit_project,
            "edit_form_state": {
                "name": edit_project.name if edit_project else "",
                "description": edit_project.description
                if edit_project and edit_project.description
                else "",
                "color": edit_project.color if edit_project else DEFAULT_PROJECT_COLOR,
            },
            "delete_errors": [],
            "delete_project": delete_project,
            "delete_confirm_value": "",
            "active_tab": "projects",
        },
        active_nav="library",
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
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
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
            active_nav="library",
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
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
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
            active_nav="library",
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
                "active_tab": "projects",
                "projects": list(repository.list_projects(connection)),
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": [],
                "form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
                "delete_errors": ["Project name confirmation does not match."],
                "delete_project": project,
                "delete_confirm_value": confirm_name,
            },
            status_code=400,
            active_nav="library",
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
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": errors,
                "form_state": {
                    "name": name,
                    "description": description or "",
                    "color": color or DEFAULT_PROJECT_COLOR,
                },
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
            },
            status_code=400,
            active_nav="library",
        )

    try:
        repository.create_project(
            connection, name=name, description=description, color=normalized_color
        )
    except sqlite3.IntegrityError:
        errors.append("Project name already exists.")
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(connection),
                "errors": errors,
                "form_state": {
                    "name": name,
                    "description": description or "",
                    "color": color or DEFAULT_PROJECT_COLOR,
                },
                "edit_errors": [],
                "edit_project": None,
                "edit_form_state": {
                    "name": "",
                    "description": "",
                    "color": DEFAULT_PROJECT_COLOR,
                },
                "delete_errors": [],
                "delete_project": None,
                "delete_confirm_value": "",
            },
            status_code=409,
            active_nav="library",
        )

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project created.",
        message_type="success",
        status_code=303,
    )
