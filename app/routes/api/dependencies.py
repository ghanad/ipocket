from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status

from app import auth, repository
from app.dependencies import get_connection
from app.models import UserRole


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = auth.get_user_id_for_token(connection, token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = repository.get_user_by_id(connection, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_editor(user=Depends(get_current_user)):
    if user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def require_editor_api_or_ui_session(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    """Allow the Editor API token or its signed browser-session representation."""

    user = require_authenticated_api_or_ui_session(
        request=request,
        authorization=authorization,
        connection=connection,
    )

    if user.role != UserRole.EDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def require_authenticated_api_or_ui_session(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    """Authenticate a bearer token or the equivalent signed browser session."""

    if authorization:
        return get_current_user(authorization=authorization, connection=connection)

    # The UI session wraps the same revocable API token in an HttpOnly,
    # signed cookie. Import lazily to keep the API dependency module small.
    from app.routes.ui._utils.session import (  # pylint: disable=import-outside-toplevel
        SESSION_COOKIE,
        _verify_session_value,
    )

    session_token = _verify_session_value(request.cookies.get(SESSION_COOKIE))
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = auth.get_user_id_for_token(connection, session_token)
    user = repository.get_user_by_id(connection, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
