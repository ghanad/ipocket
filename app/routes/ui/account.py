from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.dependencies import get_connection
from .account_password import AccountPasswordError, change_account_password
from .utils import (
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
)

router = APIRouter()


def _account_password_context(
    *,
    errors: list[str] | None = None,
) -> dict:
    return {
        "title": "ipocket - Change Password",
        "errors": errors or [],
    }


@router.get("/ui/account/password", response_class=HTMLResponse)
def ui_account_password_form(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "account_password.html",
        _account_password_context(),
        active_nav="",
    )


async def _read_password_json(request: Request) -> dict[str, str]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON request.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON object is required.")

    values: dict[str, str] = {}
    for field in (
        "current_password",
        "new_password",
        "confirm_new_password",
    ):
        value = payload.get(field, "")
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail="Password fields must be text.")
        values[field] = value
    return values


@router.post("/api/ui/account/password")
async def change_account_password_for_ui(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> dict[str, str]:
    values = await _read_password_json(request)
    try:
        change_account_password(connection, user, **values)
    except AccountPasswordError as exc:
        detail: str | list[str]
        detail = exc.messages[0] if len(exc.messages) == 1 else list(exc.messages)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    return {"message": "Password changed successfully."}


@router.post("/ui/account/password", response_class=HTMLResponse)
async def ui_account_password_submit(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> Response:
    form_data = await _parse_form_data(request)
    current_password = form_data.get("current_password") or ""
    new_password = form_data.get("new_password") or ""
    confirm_new_password = form_data.get("confirm_new_password") or ""

    try:
        change_account_password(
            connection,
            user,
            current_password=current_password,
            new_password=new_password,
            confirm_new_password=confirm_new_password,
        )
    except AccountPasswordError as exc:
        if exc.status_code == 404:
            return Response(status_code=404)
        return _render_template(
            request,
            "account_password.html",
            _account_password_context(errors=list(exc.messages)),
            active_nav="",
            status_code=400,
        )

    return _redirect_with_flash(
        request,
        "/ui/account/password",
        "Password changed successfully.",
        message_type="success",
        status_code=303,
    )
