from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from app.routes.ui.utils import _render_template
from .registry import CONNECTOR_NAMES

router = APIRouter()


@router.get("/ui/connectors", response_class=HTMLResponse)
def ui_connectors(
    request: Request,
    tab: Optional[str] = Query(default=None),
    job_id: Optional[str] = Query(default=None),
) -> HTMLResponse:
    active_tab = tab if tab in {"overview", *CONNECTOR_NAMES} else "overview"
    context = {
        "title": "ipocket - Connectors",
        "active_tab": active_tab,
        "job_id": job_id or "",
    }
    return _render_template(
        request,
        "connectors.html",
        context,
        active_nav="connectors",
    )
