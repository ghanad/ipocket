from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Optional
from urllib.parse import urljoin, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import auth, repository
from app.dependencies import get_connection
from .utils import (
    SESSION_COOKIE,
    _add_flash_message,
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    _sign_session_value,
    _verify_session_value,
)

router = APIRouter()
DEFAULT_LOGIN_REDIRECT = "/ui/ip-assets"
INVALID_LOGIN_MESSAGE = "Invalid username or password."
_LOGIN_REDIRECT_VALIDATION_ORIGIN = "https://ipocket.invalid"


@dataclass(frozen=True)
class _LoginResult:
    session_token: str
    redirect_to: str


def _approved_login_redirect(return_to: object) -> str:
    if not isinstance(return_to, str):
        return DEFAULT_LOGIN_REDIRECT
    if "\\" in return_to or any(
        unicodedata.category(character) == "Cc" for character in return_to
    ):
        return DEFAULT_LOGIN_REDIRECT

    target = return_to.strip()
    if not target.startswith("/") or target.startswith("//"):
        return DEFAULT_LOGIN_REDIRECT

    try:
        parsed_target = urlsplit(target)
        normalized_target = urlsplit(
            urljoin(f"{_LOGIN_REDIRECT_VALIDATION_ORIGIN}/", target)
        )
    except ValueError:
        return DEFAULT_LOGIN_REDIRECT

    if (
        parsed_target.scheme
        or parsed_target.netloc
        or not parsed_target.path.startswith("/")
        or parsed_target.path.startswith("//")
        or normalized_target.scheme != "https"
        or normalized_target.netloc != "ipocket.invalid"
        or not normalized_target.path.startswith("/")
        or normalized_target.path.startswith("//")
    ):
        return DEFAULT_LOGIN_REDIRECT
    return target


def _authenticate_ui_login(
    connection: sqlite3.Connection,
    *,
    username: str,
    password: str,
    return_to: object = None,
) -> Optional[_LoginResult]:
    normalized_username = username.strip()
    user = (
        repository.get_user_by_username(connection, normalized_username)
        if normalized_username
        else None
    )
    verified = False
    replacement_hash = None
    if user is not None and user.is_active:
        verified, replacement_hash = auth.verify_and_update_password(
            password, user.hashed_password
        )

    if user is None or not user.is_active or not verified:
        return None

    if replacement_hash is not None:
        repository.update_user_password(
            connection,
            user_id=user.id,
            hashed_password=replacement_hash,
        )

    return _LoginResult(
        session_token=auth.create_access_token(connection, user.id),
        redirect_to=_approved_login_redirect(return_to),
    )


def _set_login_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session_value(session_token),
        httponly=True,
        samesite="lax",
    )


async def _read_json_login_request(request: Request) -> tuple[str, str, object]:
    try:
        payload = await request.json()
    except (JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid login request.",
        ) from None
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid login request.",
        )

    username = payload.get("username")
    password = payload.get("password")
    return_to = payload.get("return_to")
    if (
        not isinstance(username, str)
        or not isinstance(password, str)
        or (return_to is not None and not isinstance(return_to, str))
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid login request.",
        )
    return username, password, return_to


@router.get("/ui/login", response_class=HTMLResponse)
def ui_login_form(request: Request, return_to: Optional[str] = None) -> HTMLResponse:
    return _render_template(
        request,
        "login.html",
        {
            "title": "ipocket - Login",
            "error_message": "",
            "return_to": return_to or "",
            "username": "",
        },
        show_nav=False,
    )


@router.post("/api/ui/login")
async def ui_login_json(
    request: Request, connection=Depends(get_connection)
) -> JSONResponse:
    username, password, return_to = await _read_json_login_request(request)
    result = _authenticate_ui_login(
        connection,
        username=username,
        password=password,
        return_to=return_to,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN_MESSAGE,
        )

    response = JSONResponse({"redirect_to": result.redirect_to})
    _set_login_cookie(response, result.session_token)
    _add_flash_message(request, response, "success", "Login successful.")
    return response


@router.post("/ui/login", response_class=HTMLResponse)
async def ui_login_submit(
    request: Request, connection=Depends(get_connection)
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""
    return_to = form_data.get("return_to")
    result = _authenticate_ui_login(
        connection,
        username=username,
        password=password,
        return_to=return_to,
    )
    if result is None:
        return _render_template(
            request,
            "login.html",
            {
                "title": "ipocket - Login",
                "error_message": INVALID_LOGIN_MESSAGE,
                "return_to": return_to or "",
                "username": username,
            },
            status_code=401,
            show_nav=False,
        )

    response = _redirect_with_flash(
        request,
        result.redirect_to,
        "Login successful.",
        message_type="success",
        status_code=303,
    )
    _set_login_cookie(response, result.session_token)
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
