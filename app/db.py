from __future__ import annotations

import sqlite3
from typing import Iterable


def connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection



def init_db(connection: sqlite3.Connection) -> None:
    schema_statements: Iterable[str] = (
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            contact TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('Viewer', 'Editor', 'Admin')),
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ip_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL UNIQUE,
            subnet TEXT NOT NULL,
            gateway TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('VM', 'PHYSICAL', 'BMC', 'VIP', 'OTHER')),
            project_id INTEGER,
            owner_id INTEGER,
            notes TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (owner_id) REFERENCES owners(id)
        )
        """,
    )

    for statement in schema_statements:
        connection.execute(statement)

    connection.commit()
