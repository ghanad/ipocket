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


def count_active_users_by_role(connection: sqlite3.Connection, role: UserRole) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role = ? AND is_active = 1",
        (role.value,),
    ).fetchone()
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


def list_users(connection: sqlite3.Connection) -> list[User]:
    rows = connection.execute("SELECT * FROM users ORDER BY username ASC").fetchall()
    return [_row_to_user(row) for row in rows]


def update_user_password(
    connection: sqlite3.Connection, user_id: int, hashed_password: str
) -> Optional[User]:
    cursor = connection.execute(
        "UPDATE users SET hashed_password = ? WHERE id = ?",
        (hashed_password, user_id),
    )
    if cursor.rowcount == 0:
        return None
    connection.commit()
    return get_user_by_id(connection, user_id)


def update_user_role(
    connection: sqlite3.Connection, user_id: int, role: UserRole
) -> Optional[User]:
    cursor = connection.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (role.value, user_id),
    )
    if cursor.rowcount == 0:
        return None
    connection.commit()
    return get_user_by_id(connection, user_id)


def set_user_active(
    connection: sqlite3.Connection, user_id: int, is_active: bool
) -> Optional[User]:
    cursor = connection.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (int(is_active), user_id),
    )
    if cursor.rowcount == 0:
        return None
    connection.commit()
    return get_user_by_id(connection, user_id)


def delete_user(connection: sqlite3.Connection, user_id: int) -> bool:
    connection.execute(
        "UPDATE audit_logs SET user_id = NULL WHERE user_id = ?", (user_id,)
    )
    cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    return cursor.rowcount > 0
