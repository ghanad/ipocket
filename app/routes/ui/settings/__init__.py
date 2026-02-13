from __future__ import annotations

from fastapi import APIRouter

from app import repository as repository
from app.utils import suggest_random_tag_color as suggest_random_tag_color

from .audit import router as audit_router
from .common import _tags_template_context, _vendors_template_context
from .projects import router as projects_router
from .tags import router as tags_router
from .vendors import router as vendors_router

router = APIRouter()
router.include_router(projects_router)
router.include_router(tags_router)
router.include_router(vendors_router)
router.include_router(audit_router)

__all__ = [
    "router",
    "repository",
    "suggest_random_tag_color",
    "_tags_template_context",
    "_vendors_template_context",
]
