from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import create_db_session


def _resolve_db_path(connection: sqlite3.Connection) -> str | None:
    row = connection.execute("PRAGMA database_list").fetchone()
    if row is None:
        return None
    return row[2] or None


@contextmanager
def session_scope(
    connection_or_session: sqlite3.Connection | Session,
) -> Iterator[Session]:
    if isinstance(connection_or_session, Session):
        yield connection_or_session
        return

    session = create_db_session(_resolve_db_path(connection_or_session))
    try:
        yield session
    finally:
        session.close()


@contextmanager
def write_session_scope(
    connection_or_session: sqlite3.Connection | Session,
) -> Iterator[Session]:
    with session_scope(connection_or_session) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def reraise_as_sqlite_integrity_error(exc: IntegrityError) -> None:
    detail = str(exc.orig) if exc.orig else str(exc)
    raise sqlite3.IntegrityError(detail) from exc
