from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from app import auth, db, repository
from app.dependencies import get_connection, get_db_path
from app.models import UserRole

SESSION_COOKIE = "ipocket_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret").encode("utf-8")
FLASH_COOKIE = "ipocket_flash"
FLASH_ALLOWED_TYPES = {"success", "info", "error", "warning"}
FLASH_MAX_MESSAGES = 5


def _sign_session_value(value: str) -> str:
    signature = hmac.new(
        SESSION_SECRET, value.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{value}.{signature}"


def _verify_session_value(value: Optional[str]) -> Optional[str]:
    if not value or "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    expected = hmac.new(
        SESSION_SECRET, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return None
    return payload


def _normalize_flash_type(value: Optional[str]) -> str:
    if not value:
        return "info"
    normalized = value.strip().lower()
    if normalized in FLASH_ALLOWED_TYPES:
        return normalized
    return "info"


def _encode_flash_payload(messages: list[dict[str, str]]) -> str:
    serialized = json.dumps(messages, separators=(",", ":"))
    return base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("utf-8")


def _decode_flash_payload(payload: str) -> Optional[str]:
    try:
        return base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None


def _load_flash_messages(request: Request) -> list[dict[str, str]]:
    signed_value = request.cookies.get(FLASH_COOKIE)
    payload = _verify_session_value(signed_value)
    if not payload:
        return []
    decoded = _decode_flash_payload(payload)
    if decoded is None:
        return []
    try:
        data = json.loads(decoded)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    messages: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        if not message:
            continue
        messages.append(
            {
                "type": _normalize_flash_type(item.get("type")),
                "message": message,
            }
        )
    return messages[:FLASH_MAX_MESSAGES]


def _store_flash_messages(response: Response, messages: list[dict[str, str]]) -> None:
    if not messages:
        return
    payload = _encode_flash_payload(messages[:FLASH_MAX_MESSAGES])
    response.set_cookie(
        FLASH_COOKIE,
        _sign_session_value(payload),
        httponly=True,
        samesite="lax",
    )


def _add_flash_message(
    request: Request,
    response: Response,
    message_type: str,
    message: str,
) -> None:
    messages = _load_flash_messages(request)
    messages.append(
        {
            "type": _normalize_flash_type(message_type),
            "message": message,
        }
    )
    _store_flash_messages(response, messages)


def _redirect_with_flash(
    request: Request,
    url: str,
    message: str,
    message_type: str = "success",
    status_code: int = 303,
) -> RedirectResponse:
    response = RedirectResponse(url=url, status_code=status_code)
    _add_flash_message(request, response, message_type, message)
    return response


def _is_authenticated_request(request: Request) -> bool:
    signed_session = request.cookies.get(SESSION_COOKIE)
    session_token = _verify_session_value(signed_session)
    if not session_token:
        return False

    connection = db.connect(get_db_path())
    try:
        user_id = auth.get_user_id_for_token(connection, session_token)
        if user_id is None:
            return False
        user = repository.get_user_by_id(connection, user_id)
    finally:
        connection.close()
    return bool(user and user.is_active)


def _is_superuser_request(request: Request) -> bool:
    signed_session = request.cookies.get(SESSION_COOKIE)
    session_token = _verify_session_value(signed_session)
    if not session_token:
        return False

    connection = db.connect(get_db_path())
    try:
        user_id = auth.get_user_id_for_token(connection, session_token)
        if user_id is None:
            return False
        user = repository.get_user_by_id(connection, user_id)
    finally:
        connection.close()
    return bool(user and user.is_active and user.role == UserRole.SUPERUSER)


def _return_to(request: Request) -> str:
    current_path = request.url.path
    query = request.url.query
    if query:
        return f"{current_path}?{query}"
    return current_path


def get_current_ui_user(request: Request, connection=Depends(get_connection)):
    signed_session = request.cookies.get(SESSION_COOKIE)
    session_token = _verify_session_value(signed_session)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/ui/login?return_to={_return_to(request)}"},
        )

    user_id = auth.get_user_id_for_token(connection, session_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/ui/login?return_to={_return_to(request)}"},
        )

    user = repository.get_user_by_id(connection, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/ui/login?return_to={_return_to(request)}"},
        )
    return user


def require_ui_editor(user=Depends(get_current_ui_user)):
    if user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def require_ui_superuser(user=Depends(get_current_ui_user)):
    if user.role != UserRole.SUPERUSER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
