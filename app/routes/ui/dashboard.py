from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

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
) -> HTMLResponse:
    return _render_template(
        request,
        "management.html",
        {"title": "ipocket - Management Overview"},
        active_nav="management",
    )
