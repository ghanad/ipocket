from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import auth, repository
from app.dependencies import get_connection
from .utils import (
    SESSION_COOKIE,
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    _sign_session_value,
    _verify_session_value,
)

router = APIRouter()


@router.get("/ui/login", response_class=HTMLResponse)
def ui_login_form(request: Request, return_to: Optional[str] = None) -> HTMLResponse:
    return _render_template(
        request,
        "login.html",
        {"title": "ipocket - Login", "error_message": "", "return_to": return_to or ""},
        show_nav=False,
    )


@router.post("/ui/login", response_class=HTMLResponse)
async def ui_login_submit(
    request: Request, connection=Depends(get_connection)
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""
    return_to = form_data.get("return_to") or "/ui/ip-assets"

    user = None
    if username:
        user = repository.get_user_by_username(connection, username)
    verified = False
    replacement_hash = None
    if user is not None and user.is_active:
        verified, replacement_hash = auth.verify_and_update_password(
            password, user.hashed_password
        )

    if user is None or not user.is_active or not verified:
        return _render_template(
            request,
            "login.html",
            {
                "title": "ipocket - Login",
                "error_message": "Invalid username or password.",
                "return_to": return_to,
            },
            status_code=401,
            show_nav=False,
        )

    if replacement_hash is not None:
        repository.update_user_password(
            connection,
            user_id=user.id,
            hashed_password=replacement_hash,
        )

    token = auth.create_access_token(connection, user.id)
    response = _redirect_with_flash(
        request,
        return_to,
        "Login successful.",
        message_type="success",
        status_code=303,
    )
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session_value(token),
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/ui/logout")
def ui_logout(request: Request, connection=Depends(get_connection)) -> Response:
    signed_session = request.cookies.get(SESSION_COOKIE)
    if signed_session:
        session_token = _verify_session_value(signed_session)
        if session_token:
            auth.revoke_access_token(connection, session_token)
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
