from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import build_info

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
        {"title": "ipocket - About", "build_info": None},
        active_nav="",
    )


@router.get("/api/ui/about")
def ui_about_data(
    _user=Depends(get_current_ui_user),
) -> dict[str, dict[str, str]]:
    display_build_info = build_info.get_display_build_info()
    return {
        "application": {"name": "ipocket"},
        "build": {
            "version": display_build_info["version"],
            "commit": display_build_info["commit"],
            "build_time": display_build_info["build_time"],
        },
        "links": {
            "health": "/health",
            "metrics": "/metrics",
        },
    }


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
