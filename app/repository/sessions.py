from __future__ import annotations

import sqlite3
from typing import Optional


def create_session(connection: sqlite3.Connection, token: str, user_id: int) -> None:
    connection.execute(
        "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
        (token, user_id),
    )
    connection.commit()


def get_session_user_id(connection: sqlite3.Connection, token: str) -> Optional[int]:
    try:
        row = connection.execute(
            "SELECT user_id FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    except sqlite3.OperationalError:
        # During transitional startup/tests before migrations create the table.
        return None
    if row is None:
        return None
    return int(row["user_id"])


def delete_session(connection: sqlite3.Connection, token: str) -> bool:
    try:
        cursor = connection.execute(
            "DELETE FROM sessions WHERE token = ?",
            (token,),
        )
    except sqlite3.OperationalError:
        return False
    connection.commit()
    return cursor.rowcount > 0


def clear_sessions(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("DELETE FROM sessions")
    except sqlite3.OperationalError:
        return
    connection.commit()
