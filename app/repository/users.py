from __future__ import annotations

import sqlite3
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.models import User, UserRole

from ._db import (
    reraise_as_sqlite_integrity_error,
    session_scope,
    write_session_scope,
)
from .mappers import _row_to_user


def create_user(
    connection_or_session: sqlite3.Connection | Session,
    username: str,
    hashed_password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    with write_session_scope(connection_or_session) as session:
        model = db_schema.User(
            username=username,
            hashed_password=hashed_password,
            role=role.value,
            is_active=1 if is_active else 0,
        )
        try:
            session.add(model)
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)
        session.refresh(model)
        return _row_to_user(
            {
                "id": model.id,
                "username": model.username,
                "hashed_password": model.hashed_password,
                "role": model.role,
                "is_active": model.is_active,
            }
        )


def count_users(connection_or_session: sqlite3.Connection | Session) -> int:
    with session_scope(connection_or_session) as session:
        total = session.scalar(select(func.count()).select_from(db_schema.User))
    return int(total or 0)


def count_active_users_by_role(
    connection_or_session: sqlite3.Connection | Session, role: UserRole
) -> int:
    with session_scope(connection_or_session) as session:
        total = session.scalar(
            select(func.count())
            .select_from(db_schema.User)
            .where(db_schema.User.role == role.value, db_schema.User.is_active == 1)
        )
    return int(total or 0)


def get_user_by_username(
    connection_or_session: sqlite3.Connection | Session, username: str
) -> Optional[User]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    db_schema.User.id,
                    db_schema.User.username,
                    db_schema.User.hashed_password,
                    db_schema.User.role,
                    db_schema.User.is_active,
                ).where(db_schema.User.username == username)
            )
            .mappings()
            .first()
        )
    return _row_to_user(row) if row else None


def get_user_by_id(
    connection_or_session: sqlite3.Connection | Session, user_id: int
) -> Optional[User]:
    with session_scope(connection_or_session) as session:
        row = (
            session.execute(
                select(
                    db_schema.User.id,
                    db_schema.User.username,
                    db_schema.User.hashed_password,
                    db_schema.User.role,
                    db_schema.User.is_active,
                ).where(db_schema.User.id == user_id)
            )
            .mappings()
            .first()
        )
    return _row_to_user(row) if row else None


def list_users(connection_or_session: sqlite3.Connection | Session) -> list[User]:
    with session_scope(connection_or_session) as session:
        rows = (
            session.execute(
                select(
                    db_schema.User.id,
                    db_schema.User.username,
                    db_schema.User.hashed_password,
                    db_schema.User.role,
                    db_schema.User.is_active,
                ).order_by(db_schema.User.username.asc())
            )
            .mappings()
            .all()
        )
    return [_row_to_user(row) for row in rows]


def update_user_password(
    connection_or_session: sqlite3.Connection | Session,
    user_id: int,
    hashed_password: str,
) -> Optional[User]:
    with write_session_scope(connection_or_session) as session:
        result = session.execute(
            update(db_schema.User)
            .where(db_schema.User.id == user_id)
            .values(hashed_password=hashed_password)
        )
        if result.rowcount == 0:
            session.rollback()
            return None
        session.commit()
    return get_user_by_id(connection_or_session, user_id)


def update_user_role(
    connection_or_session: sqlite3.Connection | Session, user_id: int, role: UserRole
) -> Optional[User]:
    with write_session_scope(connection_or_session) as session:
        result = session.execute(
            update(db_schema.User)
            .where(db_schema.User.id == user_id)
            .values(role=role.value)
        )
        if result.rowcount == 0:
            session.rollback()
            return None
        session.commit()
    return get_user_by_id(connection_or_session, user_id)


def set_user_active(
    connection_or_session: sqlite3.Connection | Session, user_id: int, is_active: bool
) -> Optional[User]:
    with write_session_scope(connection_or_session) as session:
        result = session.execute(
            update(db_schema.User)
            .where(db_schema.User.id == user_id)
            .values(is_active=1 if is_active else 0)
        )
        if result.rowcount == 0:
            session.rollback()
            return None
        session.commit()
    return get_user_by_id(connection_or_session, user_id)


def delete_user(
    connection_or_session: sqlite3.Connection | Session, user_id: int
) -> bool:
    with write_session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.AuditLog)
            .where(db_schema.AuditLog.user_id == user_id)
            .values(user_id=None)
        )
        result = session.execute(
            delete(db_schema.User).where(db_schema.User.id == user_id)
        )
        session.commit()
    return bool(result.rowcount)
