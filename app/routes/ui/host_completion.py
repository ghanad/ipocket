from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.models import UserRole

from .utils import _render_template, get_current_ui_user, require_ui_editor

router = APIRouter()


@router.get("/host-completion/analytics", response_class=HTMLResponse)
def host_completion_analytics_page(
    request: Request, user=Depends(get_current_ui_user)
) -> HTMLResponse:
    return _render_template(
        request,
        "host_completion_analytics.html",
        {
            "title": "ipocket - Host Completion Analytics",
            "can_manage_rules": user.role == UserRole.SUPERUSER,
        },
        active_nav="host-completion",
    )


@router.get("/host-completion/review", response_class=HTMLResponse)
def host_completion_review_page(
    request: Request, _user=Depends(require_ui_editor)
) -> HTMLResponse:
    return _render_template(
        request,
        "host_completion_review.html",
        {"title": "ipocket - Host Completion Review"},
        active_nav="host-completion",
    )
