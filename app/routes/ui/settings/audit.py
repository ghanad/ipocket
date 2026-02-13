from __future__ import annotations

import math
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_connection
from app.routes.ui.utils import (
    _parse_positive_int_query,
    _render_template,
    get_current_ui_user,
)

from . import repository

router = APIRouter()


@router.get("/ui/audit-log", response_class=HTMLResponse)
def ui_audit_log(
    request: Request,
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    total_count = repository.count_audit_logs(connection)
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    audit_logs = repository.list_audit_logs_paginated(
        connection,
        limit=per_page_value,
        offset=offset,
    )
    audit_log_rows = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": log.changes or "",
            "target_label": log.target_label,
        }
        for log in audit_logs
    ]
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    base_query = urlencode({"per-page": per_page_value})
    return _render_template(
        request,
        "audit_log_list.html",
        {
            "title": "ipocket - Audit Log",
            "audit_logs": audit_log_rows,
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
        active_nav="audit-log",
    )
