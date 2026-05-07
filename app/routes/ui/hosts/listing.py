from __future__ import annotations

import math
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from app import repository
from app.dependencies import get_connection
from app.utils import normalize_tag_names
from app.routes.ui.utils import (
    _parse_optional_int_query,
    _parse_positive_int_query,
    _render_template,
)

from .common import empty_host_form_state, normalize_per_page

router = APIRouter()


@router.get("/ui/hosts", response_class=HTMLResponse)
def ui_list_hosts(
    request: Request,
    q: Optional[str] = None,
    vendor_id: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    tag: Optional[list[str]] = Query(default=None),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    delete: Optional[int] = Query(default=None),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
) -> HTMLResponse:
    per_page_value = normalize_per_page(_parse_positive_int_query(per_page, 20))
    page_value = _parse_positive_int_query(page, 1)

    q_value = (q or "").strip()
    query_text = q_value or None
    vendor_filter_value = (vendor_id or "").strip()
    parsed_vendor_id = _parse_optional_int_query(vendor_filter_value)
    project_filter_value = (project_id or "").strip()
    project_unassigned_only = project_filter_value == "unassigned"
    parsed_project_id = (
        None
        if project_unassigned_only
        else _parse_optional_int_query(project_filter_value)
    )
    status_value = (status_filter or "").strip().lower()
    if status_value not in {"linked", "free"}:
        status_value = ""
    raw_tag_values = tag or []
    try:
        tag_values = normalize_tag_names(raw_tag_values) if raw_tag_values else []
    except ValueError:
        tag_values = []

    filter_args = {
        "query_text": query_text,
        "vendor_id": parsed_vendor_id,
        "project_id": parsed_project_id,
        "project_unassigned_only": project_unassigned_only,
        "asset_type": None,
        "unassigned_only": unassigned_only,
        "status_filter": status_value or None,
        "tag_names": tag_values,
    }
    total_count = repository.count_hosts(connection, **filter_args)
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    hosts = repository.list_hosts_with_ip_counts_paginated(
        connection, limit=per_page_value, offset=offset, **filter_args
    )

    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    query_params = {"per-page": per_page_value}
    if q_value:
        query_params["q"] = q_value
    if parsed_vendor_id is not None:
        query_params["vendor_id"] = parsed_vendor_id
    if project_unassigned_only:
        query_params["project_id"] = "unassigned"
    elif parsed_project_id is not None:
        query_params["project_id"] = parsed_project_id
    if tag_values:
        query_params["tag"] = tag_values
    if unassigned_only:
        query_params["unassigned-only"] = "true"
    if status_value:
        query_params["status"] = status_value
    base_query = urlencode(query_params, doseq=True)
    preserved_query_items: list[tuple[str, str]] = []
    for key, value in query_params.items():
        if key == "per-page":
            continue
        if isinstance(value, list):
            preserved_query_items.extend((key, str(item)) for item in value)
            continue
        preserved_query_items.append((key, str(value)))

    delete_host = (
        repository.get_host_by_id(connection, delete) if delete is not None else None
    )
    if delete is not None and delete_host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    delete_linked_count = 0
    if delete_host is not None:
        linked = repository.get_host_linked_assets_grouped(connection, delete_host.id)
        delete_linked_count = (
            len(linked["os"]) + len(linked["bmc"]) + len(linked["other"])
        )

    is_htmx = request.headers.get("HX-Request") is not None
    template_name = "partials/hosts_table.html" if is_htmx else "hosts.html"

    return _render_template(
        request,
        template_name,
        {
            "title": "ipocket - Hosts",
            "hosts": hosts,
            "errors": [],
            "vendors": list(repository.list_vendors(connection)),
            "projects": list(repository.list_projects(connection)),
            "tags": list(repository.list_tags(connection)),
            "form_state": empty_host_form_state(),
            "filters": {
                "q": q_value,
                "vendor_id": parsed_vendor_id,
                "project_filter": (
                    "unassigned"
                    if project_unassigned_only
                    else str(parsed_project_id or "")
                ),
                "tag": tag_values,
                "unassigned_only": unassigned_only,
                "status": status_value,
            },
            "show_search": bool(
                q_value
                or parsed_vendor_id
                or project_filter_value
                or tag_values
                or unassigned_only
                or status_value
            ),
            "show_add_host": False,
            "delete_host": delete_host,
            "delete_errors": [],
            "delete_confirm_value": "",
            "delete_linked_count": delete_linked_count,
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
                "preserved_query_items": preserved_query_items,
            },
        },
        active_nav="hosts",
    )
