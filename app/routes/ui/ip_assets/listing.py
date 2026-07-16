from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from app import repository
from app.models import IPAssetType, User, UserRole
from app.routes.ui.utils import (
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_int_query,
    _parse_positive_int_query,
    _render_template,
    get_optional_current_ui_user,
)
from app.utils import normalize_tag_names
from .helpers import _delete_requires_exact_ip

router = APIRouter()
ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


def _normalize_query_tags(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    try:
        return normalize_tag_names(values)
    except ValueError:
        return []


@dataclass(frozen=True)
class IPAssetListQuery:
    q: str
    project_id: int | None
    project_filter: str
    project_unassigned_only: bool
    project_assigned_only: bool
    asset_type: IPAssetType | None
    assigned_only: bool
    unassigned_only: bool
    archived_only: bool
    tag_all: list[str]
    tag_any: list[str]
    tag_not: list[str]
    page: int
    per_page: int


def normalize_ip_asset_list_query(
    *,
    q: str | None,
    project_id: str | None,
    tag: list[str] | None,
    tag_all: list[str] | None,
    tag_any: list[str] | None,
    tag_not: list[str] | None,
    asset_type: str | None,
    assigned_only: bool,
    unassigned_only: bool,
    archived_only: bool,
    page: str | None,
    per_page: str | None,
) -> IPAssetListQuery:
    per_page_value = _parse_positive_int_query(per_page, 20)
    if per_page_value not in ALLOWED_PAGE_SIZES:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    project_filter = (project_id or "").strip()
    project_unassigned_only = project_filter == "unassigned"
    project_assigned_only = (
        assigned_only and not unassigned_only and not project_unassigned_only
    )
    parsed_project_id = (
        None
        if project_unassigned_only
        else _parse_optional_int_query(project_filter)
    )
    try:
        asset_type_enum = _normalize_asset_type(asset_type)
    except ValueError:
        asset_type_enum = None
    tag_any_values = normalize_tag_names(
        [*_normalize_query_tags(tag), *_normalize_query_tags(tag_any)]
    )
    return IPAssetListQuery(
        q=(q or "").strip(),
        project_id=parsed_project_id,
        project_filter=(
            "unassigned"
            if project_unassigned_only
            else str(parsed_project_id or "")
        ),
        project_unassigned_only=project_unassigned_only,
        project_assigned_only=project_assigned_only,
        asset_type=asset_type_enum,
        assigned_only=project_assigned_only,
        unassigned_only=unassigned_only,
        archived_only=archived_only,
        tag_all=_normalize_query_tags(tag_all),
        tag_any=tag_any_values,
        tag_not=_normalize_query_tags(tag_not),
        page=page_value,
        per_page=per_page_value,
    )


def build_ip_asset_list_payload(
    connection,
    query: IPAssetListQuery,
    user: User | None,
) -> dict:
    total = repository.count_active_ip_assets(
        connection,
        project_id=query.project_id,
        project_unassigned_only=query.project_unassigned_only,
        project_assigned_only=query.project_assigned_only,
        asset_type=query.asset_type,
        unassigned_only=query.unassigned_only,
        query_text=query.q or None,
        tag_all_names=query.tag_all,
        tag_any_names=query.tag_any,
        tag_not_names=query.tag_not,
        archived_only=query.archived_only,
    )
    total_pages = max(1, math.ceil(total / query.per_page)) if total else 1
    page = max(1, min(query.page, total_pages))
    assets = repository.list_active_ip_assets_paginated(
        connection,
        project_id=query.project_id,
        project_unassigned_only=query.project_unassigned_only,
        project_assigned_only=query.project_assigned_only,
        asset_type=query.asset_type,
        unassigned_only=query.unassigned_only,
        query_text=query.q or None,
        tag_all_names=query.tag_all,
        tag_any_names=query.tag_any,
        tag_not_names=query.tag_not,
        limit=query.per_page,
        offset=(page - 1) * query.per_page if total else 0,
        archived_only=query.archived_only,
    )
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    tags = list(repository.list_tags(connection))
    tag_lookup = repository.list_tag_details_for_ip_assets(
        connection, [asset.id for asset in assets]
    )
    host_pair_lookup = repository.list_host_pair_ips_for_hosts(
        connection, [asset.host_id for asset in assets if asset.host_id]
    )
    rows = _build_asset_view_models(
        assets,
        {
            project.id: {"name": project.name, "color": project.color}
            for project in projects
        },
        {host.id: host.name for host in hosts},
        tag_lookup,
        host_pair_lookup,
    )
    can_edit = bool(user and user.role in {UserRole.EDITOR, UserRole.SUPERUSER})
    asset_lookup = {asset.id: asset for asset in assets}
    auto_host_enabled = _is_auto_host_for_bmc_enabled()
    for row in rows:
        source_asset = asset_lookup[row["id"]]
        row["delete_requires_exact_ip"] = _delete_requires_exact_ip(
            source_asset, [tag["name"] for tag in row["tags"]]
        )
        row["can_auto_host"] = bool(
            can_edit
            and auto_host_enabled
            and source_asset.asset_type == IPAssetType.BMC
            and source_asset.host_id is None
        )
    return {
        "assets": rows,
        "filters": {
            "projects": [
                {"id": item.id, "name": item.name, "color": item.color}
                for item in projects
            ],
            "hosts": [{"id": item.id, "name": item.name} for item in hosts],
            "tags": [
                {"id": item.id, "name": item.name, "color": item.color}
                for item in tags
            ],
            "types": [item.value for item in IPAssetType],
            "normalized": {
                "q": query.q,
                "project_id": query.project_filter,
                "type": query.asset_type.value if query.asset_type else "",
                "assigned_only": query.assigned_only,
                "unassigned_only": query.unassigned_only,
                "archived_only": query.archived_only,
                "tag_all": query.tag_all,
                "tag_any": query.tag_any,
                "tag_not": query.tag_not,
                "page": page,
                "per_page": query.per_page,
            },
        },
        "pagination": {
            "page": page,
            "per_page": query.per_page,
            "total": total,
            "total_pages": total_pages,
        },
        "can_edit": can_edit,
    }


@router.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    bulk_error: str | None = Query(default=None, alias="bulk-error"),
    bulk_success: str | None = Query(default=None, alias="bulk-success"),
    delete_error: str | None = Query(default=None, alias="delete-error"),
    delete_success: str | None = Query(default=None, alias="delete-success"),
    _user=Depends(get_optional_current_ui_user),
):
    toast_messages = [
        {"type": message_type, "message": message}
        for message_type, message in (
            ("error", bulk_error),
            ("success", bulk_success),
            ("error", delete_error),
            ("success", delete_success),
        )
        if message
    ]
    return _render_template(
        request,
        "ip_assets_list.html",
        {
            "title": "ipocket - IP Assets",
            "initial_query": request.url.query,
            "toast_messages": toast_messages,
        },
        active_nav="ip-assets",
    )
