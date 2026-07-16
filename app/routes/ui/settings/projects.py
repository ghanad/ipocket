from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_session
from app.routes.api.schemas import ProjectCreate
from app.utils import DEFAULT_PROJECT_COLOR
from app.routes.ui.utils import (
    _parse_form_data,
    _parse_optional_str,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

from . import repository
from .common import _library_react_context

router = APIRouter()


def _project_form_errors(validation_error: ValidationError) -> list[str]:
    errors: list[str] = []
    for detail in validation_error.errors():
        location = detail.get("loc") or ()
        field = location[-1] if location else ""
        if field == "name":
            message = "Project name is required."
        elif field == "color":
            message = "Project color must be a valid hex color (example: #1a2b3c)."
        else:
            message = detail.get("msg", "Invalid input.")
        if message not in errors:
            errors.append(message)
    return errors


@router.get("/ui/projects", response_class=HTMLResponse)
def ui_list_projects(
    request: Request,
    tab: Optional[str] = Query(default=None),
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    session=Depends(get_session),
) -> HTMLResponse:
    active_tab = tab if tab in {"projects", "vendors", "tags"} else "projects"
    getters = {
        "projects": (repository.get_project_by_id, "Project not found"),
        "vendors": (repository.get_vendor_by_id, "Vendor not found"),
        "tags": (repository.get_tag_by_id, "Tag not found"),
    }
    getter, not_found_message = getters[active_tab]
    if edit is not None and getter(session, edit) is None:
        raise HTTPException(status_code=404, detail=not_found_message)
    if delete is not None and getter(session, delete) is None:
        raise HTTPException(status_code=404, detail=not_found_message)

    return _render_template(
        request,
        "projects.html",
        {
            "title": "ipocket - Library",
            "library_react": True,
            "active_tab": active_tab,
            "initial_edit_id": edit,
            "initial_delete_id": delete,
            "library_bootstrap": None,
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
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    project_input: ProjectCreate | None = None
    try:
        project_input = ProjectCreate(
            name=name or None,
            description=description,
            color=color if name else None,
        )
    except ValidationError as exc:
        errors = _project_form_errors(exc)
    else:
        errors = []

    if errors:
        projects = list(repository.list_projects(session))
        edit_project = repository.get_project_by_id(session, project_id)
        if edit_project is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(session),
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
                **_library_react_context(
                    "projects",
                    "edit",
                    entity_id=project_id,
                    values={
                        "name": name,
                        "description": description or "",
                        "color": color or DEFAULT_PROJECT_COLOR,
                    },
                    errors=errors,
                ),
            },
            status_code=400,
            active_nav="library",
        )

    assert project_input is not None
    normalized_color = project_input.color or DEFAULT_PROJECT_COLOR

    try:
        updated = repository.update_project(
            session,
            project_id=project_id,
            name=project_input.name,
            description=project_input.description,
            color=normalized_color,
        )
    except IntegrityError:
        projects = list(repository.list_projects(session))
        edit_project = repository.get_project_by_id(session, project_id)
        if edit_project is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(session),
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
                **_library_react_context(
                    "projects",
                    "edit",
                    entity_id=project_id,
                    values={
                        "name": name,
                        "description": description or "",
                        "color": color or DEFAULT_PROJECT_COLOR,
                    },
                    errors=["Project name already exists."],
                ),
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
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()

    project = repository.get_project_by_id(session, project_id)
    if project is None:
        return Response(status_code=404)

    if confirm_name != project.name:
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": list(repository.list_projects(session)),
                "project_ip_counts": repository.list_project_ip_counts(session),
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
                **_library_react_context(
                    "projects",
                    "delete",
                    entity_id=project_id,
                    errors=["Project name confirmation does not match."],
                    confirm_name=confirm_name,
                ),
            },
            status_code=400,
            active_nav="library",
        )

    deleted = repository.delete_project(session, project_id)
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
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    project_input: ProjectCreate | None = None
    try:
        project_input = ProjectCreate(
            name=name or None,
            description=description,
            color=color if name else None,
        )
    except ValidationError as exc:
        errors = _project_form_errors(exc)
    else:
        errors = []

    if errors:
        projects = list(repository.list_projects(session))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(session),
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
                **_library_react_context(
                    "projects",
                    "create",
                    values={
                        "name": name,
                        "description": description or "",
                        "color": color or DEFAULT_PROJECT_COLOR,
                    },
                    errors=errors,
                ),
            },
            status_code=400,
            active_nav="library",
        )

    assert project_input is not None
    normalized_color = project_input.color or DEFAULT_PROJECT_COLOR

    try:
        repository.create_project(
            session,
            name=project_input.name,
            description=project_input.description,
            color=normalized_color,
        )
    except IntegrityError:
        errors.append("Project name already exists.")
        projects = list(repository.list_projects(session))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "active_tab": "projects",
                "projects": projects,
                "project_ip_counts": repository.list_project_ip_counts(session),
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
                **_library_react_context(
                    "projects",
                    "create",
                    values={
                        "name": name,
                        "description": description or "",
                        "color": color or DEFAULT_PROJECT_COLOR,
                    },
                    errors=errors,
                ),
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
