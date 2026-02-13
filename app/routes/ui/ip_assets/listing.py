from __future__ import annotations

import math
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.utils import normalize_tag_names
from app.routes.ui.utils import (
    _build_asset_view_models,
    _normalize_asset_type,
    _parse_optional_int_query,
    _parse_positive_int_query,
    _render_template,
)

router = APIRouter()


@router.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    tag: Optional[list[str]] = Query(default=None),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    archived_only: bool = Query(default=False, alias="archived-only"),
    bulk_error: Optional[str] = Query(default=None, alias="bulk-error"),
    bulk_success: Optional[str] = Query(default=None, alias="bulk-success"),
    delete_error: Optional[str] = Query(default=None, alias="delete-error"),
    delete_success: Optional[str] = Query(default=None, alias="delete-success"),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    project_filter_value = (project_id or "").strip()
    project_unassigned_only = project_filter_value == "unassigned"
    parsed_project_id = (
        None
        if project_unassigned_only
        else _parse_optional_int_query(project_filter_value)
    )
    try:
        asset_type_enum = _normalize_asset_type(asset_type)
    except ValueError:
        asset_type_enum = None
    q_value = (q or "").strip()
    query_text = q_value or None
    raw_tag_values = tag or []
    try:
        tag_values = normalize_tag_names(raw_tag_values) if raw_tag_values else []
    except ValueError:
        tag_values = []
    total_count = repository.count_active_ip_assets(
        connection,
        project_id=parsed_project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        archived_only=archived_only,
    )
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    assets = repository.list_active_ip_assets_paginated(
        connection,
        project_id=parsed_project_id,
        project_unassigned_only=project_unassigned_only,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        limit=per_page_value,
        offset=offset,
        archived_only=archived_only,
    )

    projects = list(repository.list_projects(connection))
    tags = list(repository.list_tags(connection))
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in projects
    }
    hosts = list(repository.list_hosts(connection))
    host_lookup = {host.id: host.name for host in hosts}
    tag_lookup = repository.list_tag_details_for_ip_assets(
        connection, [asset.id for asset in assets]
    )
    host_pair_lookup = repository.list_host_pair_ips_for_hosts(
        connection,
        [asset.host_id for asset in assets if asset.host_id],
    )
    view_models = _build_asset_view_models(
        assets,
        project_lookup,
        host_lookup,
        tag_lookup,
        host_pair_lookup,
    )

    is_htmx = request.headers.get("HX-Request") is not None
    template_name = (
        "partials/ip_assets_table.html" if is_htmx else "ip_assets_list.html"
    )
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    pagination_params: dict[str, object] = {"per-page": per_page_value}
    if q_value:
        pagination_params["q"] = q_value
    if project_unassigned_only:
        pagination_params["project_id"] = "unassigned"
    elif parsed_project_id is not None:
        pagination_params["project_id"] = parsed_project_id
    if tag_values:
        pagination_params["tag"] = tag_values
    if asset_type_enum:
        pagination_params["type"] = asset_type_enum.value
    if unassigned_only:
        pagination_params["unassigned-only"] = "true"
    if archived_only:
        pagination_params["archived-only"] = "true"
    base_query = urlencode(pagination_params, doseq=True)
    return_to = request.url.path
    if request.url.query:
        return_to = f"{return_to}?{request.url.query}"
    toast_messages: list[dict[str, str]] = []
    if bulk_error:
        toast_messages.append({"type": "error", "message": bulk_error})
    if bulk_success:
        toast_messages.append({"type": "success", "message": bulk_success})
    if delete_error:
        toast_messages.append({"type": "error", "message": delete_error})
    if delete_success:
        toast_messages.append({"type": "success", "message": delete_success})
    context = {
        "title": "ipocket - IP Assets",
        "assets": view_models,
        "projects": projects,
        "tags": tags,
        "hosts": hosts,
        "types": [asset.value for asset in IPAssetType],
        "return_to": return_to,
        "toast_messages": toast_messages,
        "pagination": {
            "page": page_value,
            "per_page": per_page_value,
            "total": total_count,
            "total_pages": total_pages,
            "has_prev": page_value > 1,
            "has_next": page_value < total_pages,
            "start_index": start_index,
            "end_index": end_index,
            "base_query": base_query,
        },
    }
    if not is_htmx:
        context.update(
            {
                "filters": {
                    "q": q or "",
                    "project_id": parsed_project_id,
                    "project_filter": (
                        "unassigned"
                        if project_unassigned_only
                        else str(parsed_project_id or "")
                    ),
                    "tag": tag_values,
                    "type": asset_type_enum.value if asset_type_enum else "",
                    "unassigned_only": unassigned_only,
                    "archived_only": archived_only,
                    "page": page_value,
                    "per_page": per_page_value,
                },
            }
        )

    return _render_template(
        request,
        template_name,
        context,
        active_nav="ip-assets",
    )
