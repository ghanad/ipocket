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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('Viewer', 'Editor', 'Admin')),
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            notes TEXT,
            vendor_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ip_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL UNIQUE,
            subnet TEXT NOT NULL,
            gateway TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('VM', 'OS', 'BMC', 'VIP', 'OTHER')),
            project_id INTEGER,
            host_id INTEGER,
            notes TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (host_id) REFERENCES hosts(id)
        )
        """,
    )

    for statement in schema_statements:
        connection.execute(statement)

    ip_asset_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(ip_assets)").fetchall()
    }
    if "host_id" not in ip_asset_columns:
        connection.execute("ALTER TABLE ip_assets ADD COLUMN host_id INTEGER REFERENCES hosts(id)")

    host_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(hosts)").fetchall()
    }
    if "vendor_id" not in host_columns:
        connection.execute("ALTER TABLE hosts ADD COLUMN vendor_id INTEGER REFERENCES vendors(id)")

    if "vendor" in host_columns:
        rows = connection.execute(
            "SELECT id, vendor FROM hosts WHERE vendor IS NOT NULL AND TRIM(vendor) <> ''"
        ).fetchall()
        for row in rows:
            vendor_name = row["vendor"].strip()
            existing = connection.execute("SELECT id FROM vendors WHERE name = ?", (vendor_name,)).fetchone()
            if existing is None:
                cursor = connection.execute("INSERT INTO vendors (name) VALUES (?)", (vendor_name,))
                vendor_id = cursor.lastrowid
            else:
                vendor_id = existing["id"]
            connection.execute("UPDATE hosts SET vendor_id = ? WHERE id = ?", (vendor_id, row["id"]))

    connection.commit()
