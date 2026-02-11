from __future__ import annotations

import sqlite3


def get_management_summary(connection: sqlite3.Connection) -> dict[str, int]:
    active_ip_row = connection.execute(
        "SELECT COUNT(*) AS total FROM ip_assets WHERE archived = 0"
    ).fetchone()
    archived_ip_row = connection.execute(
        "SELECT COUNT(*) AS total FROM ip_assets WHERE archived = 1"
    ).fetchone()
    host_row = connection.execute("SELECT COUNT(*) AS total FROM hosts").fetchone()
    vendor_row = connection.execute("SELECT COUNT(*) AS total FROM vendors").fetchone()
    project_row = connection.execute(
        "SELECT COUNT(*) AS total FROM projects"
    ).fetchone()
    return {
        "active_ip_total": int(active_ip_row["total"] or 0) if active_ip_row else 0,
        "archived_ip_total": int(archived_ip_row["total"] or 0)
        if archived_ip_row
        else 0,
        "host_total": int(host_row["total"] or 0) if host_row else 0,
        "vendor_total": int(vendor_row["total"] or 0) if vendor_row else 0,
        "project_total": int(project_row["total"] or 0) if project_row else 0,
    }
