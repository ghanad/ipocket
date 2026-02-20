from __future__ import annotations

import sqlite3
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app import schema as db_schema

from ._db import (
    reraise_as_sqlite_integrity_error,
    session_scope,
    write_session_scope,
)


def create_session(
    connection_or_session: sqlite3.Connection | Session, token: str, user_id: int
) -> None:
    with write_session_scope(connection_or_session) as session:
        try:
            session.add(db_schema.Session(token=token, user_id=user_id))
            session.commit()
        except IntegrityError as exc:
            reraise_as_sqlite_integrity_error(exc)


def get_session_user_id(
    connection_or_session: sqlite3.Connection | Session, token: str
) -> Optional[int]:
    try:
        with session_scope(connection_or_session) as session:
            user_id = session.scalar(
                select(db_schema.Session.user_id).where(
                    db_schema.Session.token == token
                )
            )
    except OperationalError:
        return None
    if user_id is None:
        return None
    return int(user_id)


def delete_session(
    connection_or_session: sqlite3.Connection | Session, token: str
) -> bool:
    try:
        with write_session_scope(connection_or_session) as session:
            result = session.execute(
                delete(db_schema.Session).where(db_schema.Session.token == token)
            )
            session.commit()
    except OperationalError:
        return False
    return bool(result.rowcount)


def clear_sessions(connection_or_session: sqlite3.Connection | Session) -> None:
    try:
        with write_session_scope(connection_or_session) as session:
            session.execute(delete(db_schema.Session))
            session.commit()
    except OperationalError:
        return
