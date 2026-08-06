from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .utils import _render_template

router = APIRouter()


@router.get("/host-completion/analytics", response_class=HTMLResponse)
def host_completion_analytics_page(request: Request) -> HTMLResponse:
    return _render_template(
        request,
        "host_completion_analytics.html",
        {"title": "ipocket - Host Completion Analytics"},
        active_nav="host-completion",
    )
