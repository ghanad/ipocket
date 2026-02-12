from __future__ import annotations

from fastapi import APIRouter

from app import repository as repository

from . import (
    auth,
    connectors,
    dashboard,
    data_ops,
    hosts,
    ip_assets,
    ranges,
    settings,
    users,
)
from .utils import (
    FLASH_COOKIE as FLASH_COOKIE,
    SESSION_COOKIE as SESSION_COOKIE,
    _encode_flash_payload as _encode_flash_payload,
    _sign_session_value as _sign_session_value,
    _is_authenticated_request as _is_authenticated_request,
    get_current_ui_user as get_current_ui_user,
    require_ui_editor as require_ui_editor,
    require_ui_superuser as require_ui_superuser,
    _is_superuser_request as _is_superuser_request,
)

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(auth.router)
router.include_router(connectors.router)
router.include_router(ip_assets.router)
router.include_router(hosts.router)
router.include_router(ranges.router)
router.include_router(settings.router)
router.include_router(users.router)
router.include_router(data_ops.router)


__all__ = [
    "router",
    "repository",
    "require_ui_editor",
    "get_current_ui_user",
    "FLASH_COOKIE",
    "SESSION_COOKIE",
    "_encode_flash_payload",
    "_sign_session_value",
    "_is_authenticated_request",
    "_is_superuser_request",
    "require_ui_superuser",
]
