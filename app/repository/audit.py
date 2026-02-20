from __future__ import annotations

import sqlite3
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import AuditLog, User

from ._db import session_scope, write_session_scope
from .mappers import _row_to_audit_log


def create_audit_log(
    connection_or_session: sqlite3.Connection | Session,
    user: Optional[User],
    action: str,
    target_type: str,
    target_id: int,
    target_label: str,
    changes: Optional[str] = None,
) -> None:
    with write_session_scope(connection_or_session) as session:
        session.add(
            db_schema.AuditLog(
                user_id=user.id if user else None,
                username=user.username if user else None,
                target_type=target_type,
                target_id=target_id,
                target_label=target_label,
                action=action,
                changes=changes,
            )
        )
        if not isinstance(connection_or_session, Session):
            session.commit()


def get_audit_logs_for_ip(
    connection_or_session: sqlite3.Connection | Session, ip_asset_id: int
) -> list[AuditLog]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
                    db_schema.AuditLog.id,
                    db_schema.AuditLog.user_id,
                    db_schema.AuditLog.username,
                    db_schema.AuditLog.target_type,
                    db_schema.AuditLog.target_id,
                    db_schema.AuditLog.target_label,
                    db_schema.AuditLog.action,
                    db_schema.AuditLog.changes,
                    db_schema.AuditLog.created_at,
                )
                .where(
                    db_schema.AuditLog.target_type == "IP_ASSET",
                    db_schema.AuditLog.target_id == ip_asset_id,
                )
                .order_by(
                    desc(db_schema.AuditLog.created_at), desc(db_schema.AuditLog.id)
                )
            )
            .mappings()
            .all()
        )
    return [_row_to_audit_log(row) for row in rows]


def list_audit_logs(
    connection_or_session: sqlite3.Connection | Session,
    target_type: Optional[str] = "IP_ASSET",
    limit: int = 200,
) -> list[AuditLog]:
    statement = select(
        db_schema.AuditLog.id,
        db_schema.AuditLog.user_id,
        db_schema.AuditLog.username,
        db_schema.AuditLog.target_type,
        db_schema.AuditLog.target_id,
        db_schema.AuditLog.target_label,
        db_schema.AuditLog.action,
        db_schema.AuditLog.changes,
        db_schema.AuditLog.created_at,
    )
    if target_type is not None:
        statement = statement.where(db_schema.AuditLog.target_type == target_type)
    statement = statement.order_by(
        desc(db_schema.AuditLog.created_at), desc(db_schema.AuditLog.id)
    ).limit(limit)
    with session_scope(connection_or_session) as session:
        rows = session.execute(statement).mappings().all()
    return [_row_to_audit_log(row) for row in rows]


def count_audit_logs(
    connection_or_session: sqlite3.Connection | Session,
    target_type: Optional[str] = "IP_ASSET",
) -> int:
    statement = select(func.count()).select_from(db_schema.AuditLog)
    if target_type is not None:
        statement = statement.where(db_schema.AuditLog.target_type == target_type)
    with session_scope(connection_or_session) as session:
        total = session.scalar(statement)
    return int(total or 0)


def list_audit_logs_paginated(
    connection_or_session: sqlite3.Connection | Session,
    target_type: Optional[str] = "IP_ASSET",
    limit: int = 20,
    offset: int = 0,
) -> list[AuditLog]:
    statement = select(
        db_schema.AuditLog.id,
        db_schema.AuditLog.user_id,
        db_schema.AuditLog.username,
        db_schema.AuditLog.target_type,
        db_schema.AuditLog.target_id,
        db_schema.AuditLog.target_label,
        db_schema.AuditLog.action,
        db_schema.AuditLog.changes,
        db_schema.AuditLog.created_at,
    )
    if target_type is not None:
        statement = statement.where(db_schema.AuditLog.target_type == target_type)
    statement = (
        statement.order_by(
            desc(db_schema.AuditLog.created_at), desc(db_schema.AuditLog.id)
        )
        .limit(limit)
        .offset(offset)
    )
    with session_scope(connection_or_session) as session:
        rows = session.execute(statement).mappings().all()
    return [_row_to_audit_log(row) for row in rows]
