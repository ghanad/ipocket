from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import AuditLog, User
from .mappers import _row_to_audit_log


def create_audit_log(
    connection: sqlite3.Connection,
    user: Optional[User],
    action: str,
    target_type: str,
    target_id: int,
    target_label: str,
    changes: Optional[str] = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (
            user_id,
            username,
            target_type,
            target_id,
            target_label,
            action,
            changes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.id if user else None,
            user.username if user else None,
            target_type,
            target_id,
            target_label,
            action,
            changes,
        ),
    )


def get_audit_logs_for_ip(
    connection: sqlite3.Connection, ip_asset_id: int
) -> list[AuditLog]:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_logs
        WHERE target_type = 'IP_ASSET'
          AND target_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (ip_asset_id,),
    ).fetchall()
    return [_row_to_audit_log(row) for row in rows]


def list_audit_logs(
    connection: sqlite3.Connection,
    target_type: str = "IP_ASSET",
    limit: int = 200,
) -> list[AuditLog]:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_logs
        WHERE target_type = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (target_type, limit),
    ).fetchall()
    return [_row_to_audit_log(row) for row in rows]


def count_audit_logs(
    connection: sqlite3.Connection,
    target_type: str = "IP_ASSET",
) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM audit_logs
        WHERE target_type = ?
        """,
        (target_type,),
    ).fetchone()
    return row["count"] if row else 0


def list_audit_logs_paginated(
    connection: sqlite3.Connection,
    target_type: str = "IP_ASSET",
    limit: int = 20,
    offset: int = 0,
) -> list[AuditLog]:
    rows = connection.execute(
        """
        SELECT *
        FROM audit_logs
        WHERE target_type = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (target_type, limit, offset),
    ).fetchall()
    return [_row_to_audit_log(row) for row in rows]
