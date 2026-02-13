from __future__ import annotations

from fastapi import APIRouter

from .detail import router as detail_router
from .listing import router as listing_router
from .mutations import router as mutations_router

router = APIRouter()
router.include_router(listing_router)
router.include_router(mutations_router)
router.include_router(detail_router)

__all__ = ["router"]
