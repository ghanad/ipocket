from __future__ import annotations

import sqlite3

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import schema as db_schema

from ._db import session_scope


def get_management_summary(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, int]:
    with session_scope(connection_or_session) as session:
        active_ip_total = session.scalar(
            select(func.count())
            .select_from(db_schema.IPAsset)
            .where(db_schema.IPAsset.archived == 0)
        )
        archived_ip_total = session.scalar(
            select(func.count())
            .select_from(db_schema.IPAsset)
            .where(db_schema.IPAsset.archived == 1)
        )
        host_total = session.scalar(select(func.count()).select_from(db_schema.Host))
        vendor_total = session.scalar(
            select(func.count()).select_from(db_schema.Vendor)
        )
        project_total = session.scalar(
            select(func.count()).select_from(db_schema.Project)
        )
    return {
        "active_ip_total": int(active_ip_total or 0),
        "archived_ip_total": int(archived_ip_total or 0),
        "host_total": int(host_total or 0),
        "vendor_total": int(vendor_total or 0),
        "project_total": int(project_total or 0),
    }
