from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

import app.routes.ui.settings as settings_routes

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_session
from app.routes.api.schemas import TagCreate, TagUpdate
from app.utils import DEFAULT_TAG_COLOR
from app.routes.ui.utils import (
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

from . import repository
from .common import _tags_template_context

router = APIRouter()


def _tag_form_errors(validation_error: ValidationError) -> list[str]:
    errors: list[str] = []
    for detail in validation_error.errors():
        location = detail.get("loc") or ()
        field = location[-1] if location else ""
        message = detail.get("msg", "Invalid input.")
        if field == "name" and message == "Input should be a valid string":
            message = "Tag name is required."
        elif field == "color":
            message = "Tag color must be a valid hex color (example: #1a2b3c)."
        if message not in errors:
            errors.append(message)
    return errors


@router.get("/ui/tags", response_class=HTMLResponse)
def ui_list_tags(
    request: Request,
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    session=Depends(get_session),
) -> HTMLResponse:
    edit_tag = None
    delete_tag = None
    if edit is not None:
        edit_tag = repository.get_tag_by_id(session, edit)
        if edit_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")
    if delete is not None:
        delete_tag = repository.get_tag_by_id(session, delete)
        if delete_tag is None:
            raise HTTPException(status_code=404, detail="Tag not found")

    return _render_template(
        request,
        "projects.html",
        _tags_template_context(session, edit_tag=edit_tag, delete_tag=delete_tag),
        active_nav="library",
    )


@router.get("/ui/tags/{tag_id}/edit", response_class=HTMLResponse)
def ui_open_tag_edit(
    tag_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/projects?{urlencode({'tab': 'tags', 'edit': tag_id})}",
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
        f"/ui/projects?{urlencode({'tab': 'tags', 'delete': tag_id})}",
        "",
        status_code=303,
    )


@router.post("/ui/tags", response_class=HTMLResponse)
async def ui_create_tag(
    request: Request,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    tag_input: TagCreate | None = None
    try:
        tag_input = TagCreate(name=name or None, color=color if name else None)
    except ValidationError as exc:
        errors = _tag_form_errors(exc)
    else:
        errors = []

    if errors:
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                session,
                errors=errors,
                form_state={
                    "name": name,
                    "color": color or settings_routes.suggest_random_tag_color(),
                },
            ),
            status_code=400,
            active_nav="library",
        )

    assert tag_input is not None
    normalized_color = tag_input.color or settings_routes.suggest_random_tag_color()

    try:
        repository.create_tag(session, name=tag_input.name, color=normalized_color)
    except IntegrityError:
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                session,
                errors=["Tag name already exists."],
                form_state={
                    "name": name,
                    "color": color or settings_routes.suggest_random_tag_color(),
                },
            ),
            status_code=409,
            active_nav="library",
        )

    return _redirect_with_flash(
        request,
        "/ui/projects?tab=tags",
        "Tag created.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/tags/{tag_id}/edit", response_class=HTMLResponse)
async def ui_edit_tag(
    tag_id: int,
    request: Request,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    tag_input: TagUpdate | None = None
    try:
        tag_input = TagUpdate(name=name or None, color=color if name else None)
    except ValidationError as exc:
        errors = _tag_form_errors(exc)
    else:
        errors = []

    if errors:
        edit_tag = repository.get_tag_by_id(session, tag_id)
        if edit_tag is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                session,
                edit_errors=errors,
                edit_tag=edit_tag,
                edit_form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=400,
            active_nav="library",
        )

    assert tag_input is not None
    normalized_color = tag_input.color or DEFAULT_TAG_COLOR

    try:
        updated = repository.update_tag(
            session, tag_id, tag_input.name, normalized_color
        )
    except IntegrityError:
        edit_tag = repository.get_tag_by_id(session, tag_id)
        if edit_tag is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                session,
                edit_errors=["Tag name already exists."],
                edit_tag=edit_tag,
                edit_form_state={"name": name, "color": color or DEFAULT_TAG_COLOR},
            ),
            status_code=409,
            active_nav="library",
        )

    if updated is None:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/projects?tab=tags",
        "Tag updated.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/tags/{tag_id}/delete", response_class=HTMLResponse)
async def ui_delete_tag(
    tag_id: int,
    request: Request,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()

    tag = repository.get_tag_by_id(session, tag_id)
    if tag is None:
        return Response(status_code=404)

    if confirm_name != tag.name:
        return _render_template(
            request,
            "projects.html",
            _tags_template_context(
                session,
                delete_errors=["Tag name confirmation does not match."],
                delete_tag=tag,
                delete_confirm_value=confirm_name,
            ),
            status_code=400,
            active_nav="library",
        )

    deleted = repository.delete_tag(session, tag_id)
    if not deleted:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/projects?tab=tags",
        "Tag deleted.",
        message_type="success",
        status_code=303,
    )
