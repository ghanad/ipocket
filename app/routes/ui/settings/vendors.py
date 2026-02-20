from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_session
from app.routes.api.schemas import VendorCreate, VendorUpdate
from app.routes.ui.utils import (
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
    require_ui_editor,
)

from . import repository
from .common import _vendors_template_context

router = APIRouter()


def _vendor_form_errors(validation_error: ValidationError) -> list[str]:
    errors: list[str] = []
    for detail in validation_error.errors():
        location = detail.get("loc") or ()
        field = location[-1] if location else ""
        if field == "name":
            message = "Vendor name is required."
        else:
            message = detail.get("msg", "Invalid input.")
        if message not in errors:
            errors.append(message)
    return errors


@router.get("/ui/vendors", response_class=HTMLResponse)
def ui_list_vendors(
    request: Request,
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    session=Depends(get_session),
) -> HTMLResponse:
    edit_vendor = None
    delete_vendor = None
    if edit is not None:
        edit_vendor = repository.get_vendor_by_id(session, edit)
        if edit_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")
    if delete is not None:
        delete_vendor = repository.get_vendor_by_id(session, delete)
        if delete_vendor is None:
            raise HTTPException(status_code=404, detail="Vendor not found")

    return _render_template(
        request,
        "projects.html",
        _vendors_template_context(
            session, edit_vendor=edit_vendor, delete_vendor=delete_vendor
        ),
        active_nav="library",
    )


@router.get("/ui/vendors/{vendor_id}/edit", response_class=HTMLResponse)
def ui_open_vendor_edit(
    vendor_id: int,
    request: Request,
    _user=Depends(get_current_ui_user),
) -> RedirectResponse:
    return _redirect_with_flash(
        request,
        f"/ui/projects?{urlencode({'tab': 'vendors', 'edit': vendor_id})}",
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
        f"/ui/projects?{urlencode({'tab': 'vendors', 'delete': vendor_id})}",
        "",
        status_code=303,
    )


@router.post("/ui/vendors", response_class=HTMLResponse)
async def ui_create_vendor(
    request: Request,
    edit: Optional[int] = Query(default=None),
    delete: Optional[int] = Query(default=None),
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()

    edit_vendor = (
        repository.get_vendor_by_id(session, edit) if edit is not None else None
    )
    delete_vendor = (
        repository.get_vendor_by_id(session, delete) if delete is not None else None
    )

    vendor_input: VendorCreate | None = None
    try:
        vendor_input = VendorCreate(name=name or None)
    except ValidationError as exc:
        errors = _vendor_form_errors(exc)
    else:
        errors = []

    if errors:
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                session,
                errors=errors,
                form_state={"name": name},
                edit_vendor=edit_vendor,
                delete_vendor=delete_vendor,
            ),
            status_code=400,
            active_nav="library",
        )

    assert vendor_input is not None
    try:
        repository.create_vendor(session, name=vendor_input.name)
    except IntegrityError:
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                session,
                errors=["Vendor name already exists."],
                form_state={"name": name},
                edit_vendor=edit_vendor,
                delete_vendor=delete_vendor,
            ),
            status_code=409,
            active_nav="library",
        )
    return _redirect_with_flash(
        request,
        "/ui/projects?tab=vendors",
        "Vendor created.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/vendors/{vendor_id}/edit", response_class=HTMLResponse)
async def ui_edit_vendor(
    vendor_id: int,
    request: Request,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    vendor_input: VendorUpdate | None = None
    try:
        vendor_input = VendorUpdate(name=name or None)
    except ValidationError as exc:
        errors = _vendor_form_errors(exc)
    else:
        errors = []

    if errors:
        edit_vendor = repository.get_vendor_by_id(session, vendor_id)
        if edit_vendor is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                session,
                edit_errors=errors,
                edit_vendor=edit_vendor,
                edit_form_state={"name": name},
            ),
            status_code=400,
            active_nav="library",
        )

    assert vendor_input is not None
    try:
        updated = repository.update_vendor(session, vendor_id, vendor_input.name)
    except IntegrityError:
        edit_vendor = repository.get_vendor_by_id(session, vendor_id)
        if edit_vendor is None:
            return Response(status_code=404)
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                session,
                edit_errors=["Vendor name already exists."],
                edit_vendor=edit_vendor,
                edit_form_state={"name": name},
            ),
            status_code=409,
            active_nav="library",
        )
    if updated is None:
        return Response(status_code=404)
    return _redirect_with_flash(
        request,
        "/ui/projects?tab=vendors",
        "Vendor updated.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/vendors/{vendor_id}/delete", response_class=HTMLResponse)
async def ui_delete_vendor(
    vendor_id: int,
    request: Request,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    vendor = repository.get_vendor_by_id(session, vendor_id)
    if vendor is None:
        return Response(status_code=404)

    if confirm_name != vendor.name:
        return _render_template(
            request,
            "projects.html",
            _vendors_template_context(
                session,
                delete_errors=["Vendor name confirmation does not match."],
                delete_vendor=vendor,
                delete_confirm_value=confirm_name,
            ),
            status_code=400,
            active_nav="library",
        )

    deleted = repository.delete_vendor(session, vendor_id)
    if not deleted:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/projects?tab=vendors",
        "Vendor deleted.",
        message_type="success",
        status_code=303,
    )
