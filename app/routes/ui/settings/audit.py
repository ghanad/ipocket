from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

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
ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


@dataclass(frozen=True)
class AuditLogQuery:
    page: int
    per_page: int


def normalize_audit_log_query(
    page: Optional[str],
    per_page: Optional[str],
) -> AuditLogQuery:
    per_page_value = _parse_positive_int_query(per_page, 20)
    if per_page_value not in ALLOWED_PAGE_SIZES:
        per_page_value = 20
    return AuditLogQuery(
        page=_parse_positive_int_query(page, 1),
        per_page=per_page_value,
    )


def build_audit_log_payload(connection, query: AuditLogQuery) -> dict:
    total = repository.count_audit_logs(connection, target_type=None)
    total_pages = max(1, math.ceil(total / query.per_page)) if total else 1
    page = max(1, min(query.page, total_pages))
    rows = repository.list_audit_logs_paginated(
        connection,
        target_type=None,
        limit=query.per_page,
        offset=(page - 1) * query.per_page if total else 0,
    )
    normalized_query = {"page": page, "per_page": query.per_page}
    return {
        "audit_logs": [
            {
                "id": log.id,
                "created_at": log.created_at,
                "target_label": log.target_label,
                "username": log.username or "System",
                "action": log.action,
                "changes": log.changes or "",
            }
            for log in rows
        ],
        "pagination": {
            **normalized_query,
            "total": total,
            "total_pages": total_pages,
        },
        "query": normalized_query,
    }


@router.get("/ui/audit-log", response_class=HTMLResponse)
def ui_audit_log(
    request: Request,
    _user=Depends(get_current_ui_user),
):
    return _render_template(
        request,
        "audit_log_list.html",
        {
            "title": "ipocket - Audit Log",
            "initial_query": str(request.url.query),
        },
        active_nav="audit-log",
    )


@router.get("/api/ui/audit-log")
def list_audit_logs_for_ui(
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    query = normalize_audit_log_query(page, per_page)
    return build_audit_log_payload(connection, query)
