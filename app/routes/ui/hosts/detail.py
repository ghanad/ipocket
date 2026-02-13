from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app import repository
from app.dependencies import get_connection
from app.routes.ui.utils import (
    _redirect_with_flash,
    _render_template,
    require_ui_editor,
)

router = APIRouter()


@router.get("/ui/hosts/{host_id}", response_class=HTMLResponse)
def ui_host_detail(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
) -> HTMLResponse:
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    return _render_template(
        request,
        "host_detail.html",
        {
            "title": "ipocket - Host Detail",
            "host": host,
            "os_assets": grouped["os"],
            "bmc_assets": grouped["bmc"],
            "other_assets": grouped["other"],
        },
        active_nav="hosts",
    )


@router.get("/ui/hosts/{host_id}/delete", response_class=HTMLResponse)
def ui_delete_host_confirm(
    request: Request,
    host_id: int,
    _user=Depends(require_ui_editor),
):
    return _redirect_with_flash(
        request,
        f"/ui/hosts?{urlencode({'delete': host_id})}",
        "",
        status_code=303,
    )
