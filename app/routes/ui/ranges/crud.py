from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_connection
from app.utils import normalize_cidr
from app.routes.ui.utils import (
    _parse_optional_int,
    _parse_optional_str,
    _render_template,
    require_ui_editor,
)

from . import repository
from .common import _build_range_table_rows

router = APIRouter()


@router.get("/ui/ranges", response_class=HTMLResponse)
def ui_list_ranges(
    request: Request, connection=Depends(get_connection)
) -> HTMLResponse:
    edit_param = request.query_params.get("edit")
    edit_range_id = _parse_optional_int(edit_param)
    edit_ip_range = (
        repository.get_ip_range_by_id(connection, edit_range_id)
        if edit_range_id
        else None
    )
    delete_param = request.query_params.get("delete")
    delete_range_id = _parse_optional_int(delete_param)
    delete_ip_range = (
        repository.get_ip_range_by_id(connection, delete_range_id)
        if delete_range_id
        else None
    )
    ranges = list(repository.list_ip_ranges(connection))
    utilization = repository.get_ip_range_utilization(connection)
    range_rows = _build_range_table_rows(ranges, utilization)
    return _render_template(
        request,
        "ranges.html",
        {
            "title": "ipocket - IP Ranges",
            "range_rows": range_rows,
            "errors": [],
            "form_state": {"name": "", "cidr": "", "notes": ""},
            "edit_errors": [],
            "edit_form_state": {
                "name": edit_ip_range.name if edit_ip_range else "",
                "cidr": edit_ip_range.cidr if edit_ip_range else "",
                "notes": edit_ip_range.notes if edit_ip_range else "",
            },
            "edit_ip_range": edit_ip_range,
            "delete_errors": [],
            "delete_confirm_value": "",
            "delete_ip_range": delete_ip_range,
        },
        active_nav="ranges",
    )


@router.post("/ui/ranges", response_class=HTMLResponse)
async def ui_create_range(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await request.form()
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append(
                "CIDR must be a valid IPv4 network (example: 192.168.10.0/24)."
            )

    if errors:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        range_rows = _build_range_table_rows(ranges, utilization)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": range_rows,
                "errors": errors,
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        repository.create_ip_range(
            connection, name=name, cidr=normalized_cidr or cidr, notes=notes
        )
    except sqlite3.IntegrityError:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        range_rows = _build_range_table_rows(ranges, utilization)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": range_rows,
                "errors": ["CIDR already exists."],
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=409,
            active_nav="ranges",
        )

    return RedirectResponse(url="/ui/ranges", status_code=303)


@router.get("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
def ui_edit_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    if repository.get_ip_range_by_id(connection, range_id) is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url=f"/ui/ranges?edit={range_id}", status_code=303)


@router.post("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
async def ui_update_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await request.form()
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append(
                "CIDR must be a valid IPv4 network (example: 192.168.10.0/24)."
            )

    if errors:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": errors,
                "edit_form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_ip_range": ip_range,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        updated_range = repository.update_ip_range(
            connection,
            range_id,
            name=name,
            cidr=normalized_cidr or cidr,
            notes=notes,
        )
    except sqlite3.IntegrityError:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": ["CIDR already exists."],
                "edit_form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
                "edit_ip_range": ip_range,
                "delete_errors": [],
                "delete_confirm_value": "",
                "delete_ip_range": None,
            },
            status_code=409,
            active_nav="ranges",
        )

    if updated_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    return RedirectResponse(url="/ui/ranges", status_code=303)


@router.get("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
def ui_delete_range_confirm(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url=f"/ui/ranges?delete={range_id}", status_code=303)


@router.post("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
async def ui_delete_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await request.form()
    confirm_name = (form_data.get("confirm_name") or "").strip()
    if confirm_name != ip_range.name:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "range_rows": _build_range_table_rows(ranges, utilization),
                "errors": [],
                "form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_errors": [],
                "edit_form_state": {"name": "", "cidr": "", "notes": ""},
                "edit_ip_range": None,
                "delete_errors": ["برای حذف کامل، نام رنج را دقیقاً وارد کنید."],
                "delete_confirm_value": confirm_name,
                "delete_ip_range": ip_range,
            },
            status_code=400,
            active_nav="ranges",
        )

    deleted = repository.delete_ip_range(connection, range_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url="/ui/ranges", status_code=303)
