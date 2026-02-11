from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import get_connection
from app import repository
from .utils import _render_template, get_current_ui_user

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return RedirectResponse(url="/ui/ip-assets")


@router.get("/ui/about", response_class=HTMLResponse)
def ui_about(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "about.html",
        {"title": "ipocket - About"},
        active_nav="",
    )


@router.get("/ui/management", response_class=HTMLResponse)
def ui_management(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    summary = repository.get_management_summary(connection)
    utilization = repository.get_ip_range_utilization(connection)
    return _render_template(
        request,
        "management.html",
        {
            "title": "ipocket - Management Overview",
            "summary": summary,
            "utilization": utilization,
        },
        active_nav="management",
    )
