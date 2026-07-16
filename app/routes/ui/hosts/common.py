from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from app.models import UserRole
from app.routes.ui.utils import get_current_ui_user


_ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


def normalize_per_page(value: int, default: int = 20) -> int:
    if value not in _ALLOWED_PAGE_SIZES:
        return default
    return value


def empty_host_form_state() -> dict[str, Any]:
    return {
        "name": "",
        "notes": "",
        "vendor_id": "",
        "os_ips": "",
        "bmc_ips": "",
    }


def require_ui_host_writer(user=Depends(get_current_ui_user)):
    if user.role not in {UserRole.EDITOR, UserRole.SUPERUSER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
