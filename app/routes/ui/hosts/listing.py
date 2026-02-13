from __future__ import annotations

import math
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from app import repository
from app.dependencies import get_connection
from app.routes.ui.utils import (
    _parse_positive_int_query,
    _render_template,
)

from .common import empty_host_form_state, normalize_per_page

router = APIRouter()


@router.get("/ui/hosts", response_class=HTMLResponse)
def ui_list_hosts(
    request: Request,
    q: Optional[str] = None,
    delete: Optional[int] = Query(default=None),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
) -> HTMLResponse:
    per_page_value = normalize_per_page(_parse_positive_int_query(per_page, 20))
    page_value = _parse_positive_int_query(page, 1)

    q_value = (q or "").strip()
    if q_value:
        all_hosts = repository.list_hosts_with_ip_counts(connection)
        q_lower = q_value.lower()
        filtered_hosts = [
            host
            for host in all_hosts
            if q_lower in (host["name"] or "").lower()
            or q_lower in (host["notes"] or "").lower()
            or q_lower in (host["vendor"] or "").lower()
            or q_lower in (host["project_name"] or "").lower()
            or q_lower in (host["os_ips"] or "").lower()
            or q_lower in (host["bmc_ips"] or "").lower()
        ]
        total_count = len(filtered_hosts)
        total_pages = (
            max(1, math.ceil(total_count / per_page_value)) if total_count else 1
        )
        page_value = max(1, min(page_value, total_pages))
        offset = (page_value - 1) * per_page_value if total_count else 0
        hosts = filtered_hosts[offset : offset + per_page_value]
    else:
        total_count = repository.count_hosts(connection)
        total_pages = (
            max(1, math.ceil(total_count / per_page_value)) if total_count else 1
        )
        page_value = max(1, min(page_value, total_pages))
        offset = (page_value - 1) * per_page_value if total_count else 0
        hosts = repository.list_hosts_with_ip_counts_paginated(
            connection, limit=per_page_value, offset=offset
        )

    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    query_params = {"per-page": per_page_value}
    if q_value:
        query_params["q"] = q_value
    base_query = urlencode(query_params)

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

    return _render_template(
        request,
        "hosts.html",
        {
            "title": "ipocket - Hosts",
            "hosts": hosts,
            "errors": [],
            "vendors": list(repository.list_vendors(connection)),
            "projects": list(repository.list_projects(connection)),
            "form_state": empty_host_form_state(),
            "filters": {"q": q_value},
            "show_search": bool(q_value),
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
            },
        },
        active_nav="hosts",
    )
