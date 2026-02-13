from __future__ import annotations

from fastapi import APIRouter

from app import repository as repository

from .addresses import router as addresses_router
from .common import _parse_selected_tags
from .crud import router as crud_router

router = APIRouter()
router.include_router(crud_router)
router.include_router(addresses_router)

__all__ = ["router", "repository", "_parse_selected_tags"]
