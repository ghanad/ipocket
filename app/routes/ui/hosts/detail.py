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
from app.routes.ui._utils.assets import _build_asset_view_models

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
    linked_assets = [*grouped["os"], *grouped["bmc"], *grouped["other"]]
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in repository.list_projects(connection)
    }
    tag_lookup = repository.list_tag_details_for_ip_assets(
        connection, [asset.id for asset in linked_assets]
    )
    host_lookup = {host.id: host.name}
    view_models = _build_asset_view_models(
        linked_assets,
        project_lookup,
        host_lookup,
        tag_lookup,
    )
    view_models_by_id = {asset["id"]: asset for asset in view_models}
    return _render_template(
        request,
        "host_detail.html",
        {
            "title": "ipocket - Host Detail",
            "host": host,
            "os_assets": [view_models_by_id[asset.id] for asset in grouped["os"]],
            "bmc_assets": [view_models_by_id[asset.id] for asset in grouped["bmc"]],
            "other_assets": [view_models_by_id[asset.id] for asset in grouped["other"]],
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
