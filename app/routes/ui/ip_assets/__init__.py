from __future__ import annotations

from fastapi import APIRouter

from app.routes.ui.utils import _parse_optional_int

from .actions import router as actions_router
from .forms import router as forms_router
from .helpers import (
    _delete_requires_exact_ip,
    _friendly_audit_changes,
    _parse_selected_tags,
)
from .listing import router as listing_router

router = APIRouter()
router.include_router(listing_router)
router.include_router(actions_router)
router.include_router(forms_router)

__all__ = [
    "router",
    "_friendly_audit_changes",
    "_parse_selected_tags",
    "_delete_requires_exact_ip",
    "_parse_optional_int",
]
