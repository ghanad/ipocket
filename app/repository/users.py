from __future__ import annotations

import sqlite3
from typing import Optional

from app.models import User, UserRole
from .mappers import _row_to_user


def create_user(
    connection: sqlite3.Connection,
    username: str,
    hashed_password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    cursor = connection.execute(
        "INSERT INTO users (username, hashed_password, role, is_active) VALUES (?, ?, ?, ?)",
        (username, hashed_password, role.value, int(is_active)),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch newly created user.")
    return _row_to_user(row)


def count_users(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return int(row["total"] or 0) if row else 0


def get_user_by_username(
    connection: sqlite3.Connection, username: str
) -> Optional[User]:
    row = connection.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> Optional[User]:
    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None
