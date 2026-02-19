from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def connect(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA synchronous=NORMAL;")
    connection.execute("PRAGMA busy_timeout=5000;")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(connection: sqlite3.Connection) -> None:
    run_migrations(connection=connection)


def run_migrations(
    *, connection: sqlite3.Connection | None = None, db_path: str | None = None
) -> None:
    if connection is None and db_path is None:
        db_path = os.getenv("IPAM_DB_PATH", "ipocket.db")

    if connection is not None and db_path is None:
        db_path = _get_connection_path(connection)

    if connection is None and db_path is None:
        raise ValueError("Either connection or db_path must be provided.")

    config = _alembic_config(db_path or "ipocket.db")
    if connection is not None:
        connection.execute("PRAGMA foreign_keys = ON")

    if connection is not None and _needs_legacy_stamp(connection):
        _apply_legacy_migrations(connection)
        command.stamp(config, "head")
        return

    command.upgrade(config, "head")


def _alembic_config(db_path: str) -> Config:
    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _get_connection_path(connection: sqlite3.Connection) -> str:
    row = connection.execute("PRAGMA database_list").fetchone()
    if row is None:
        return "ipocket.db"
    return row[2] or "ipocket.db"


def _needs_legacy_stamp(connection: sqlite3.Connection) -> bool:
    if _has_table(connection, "alembic_version"):
        return False
    return any(
        _has_table(connection, table)
        for table in ("projects", "users", "vendors", "hosts", "ip_assets")
    )


def _has_table(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _apply_legacy_migrations(connection: sqlite3.Connection) -> None:
    if not _has_table(connection, "vendors"):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    if not _has_table(connection, "ip_ranges"):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_ranges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cidr TEXT NOT NULL UNIQUE,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    if _has_table(connection, "ip_assets"):
        ip_asset_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(ip_assets)").fetchall()
        }
        if "host_id" not in ip_asset_columns:
            connection.execute(
                "ALTER TABLE ip_assets ADD COLUMN host_id INTEGER REFERENCES hosts(id)"
            )

    if _has_table(connection, "hosts"):
        host_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(hosts)").fetchall()
        }
        if "vendor_id" not in host_columns:
            connection.execute(
                "ALTER TABLE hosts ADD COLUMN vendor_id INTEGER REFERENCES vendors(id)"
            )

        if "vendor" in host_columns:
            rows = connection.execute(
                "SELECT id, vendor FROM hosts WHERE vendor IS NOT NULL AND TRIM(vendor) <> ''"
            ).fetchall()
            for row in rows:
                vendor_name = row["vendor"].strip()
                existing = connection.execute(
                    "SELECT id FROM vendors WHERE name = ?",
                    (vendor_name,),
                ).fetchone()
                if existing is None:
                    cursor = connection.execute(
                        "INSERT INTO vendors (name) VALUES (?)", (vendor_name,)
                    )
                    vendor_id = cursor.lastrowid
                else:
                    vendor_id = existing["id"]
                connection.execute(
                    "UPDATE hosts SET vendor_id = ? WHERE id = ?",
                    (vendor_id, row["id"]),
                )

    if _has_table(connection, "projects"):
        project_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "color" not in project_columns:
            connection.execute(
                "ALTER TABLE projects ADD COLUMN color TEXT NOT NULL DEFAULT '#94a3b8'"
            )

    _drop_legacy_ip_asset_addressing(connection)

    connection.commit()


def _drop_legacy_ip_asset_addressing(connection: sqlite3.Connection) -> None:
    if not _has_table(connection, "ip_assets"):
        return
    columns = [
        row["name"]
        for row in connection.execute("PRAGMA table_info(ip_assets)").fetchall()
    ]
    if "subnet" not in columns and "gateway" not in columns:
        return

    select_host_id = "host_id" if "host_id" in columns else "NULL AS host_id"
    select_notes = "notes" if "notes" in columns else "NULL AS notes"
    select_archived = "archived" if "archived" in columns else "0 AS archived"
    select_created_at = (
        "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP AS created_at"
    )
    select_updated_at = (
        "updated_at" if "updated_at" in columns else "CURRENT_TIMESTAMP AS updated_at"
    )

    connection.execute("ALTER TABLE ip_assets RENAME TO ip_assets_old")
    connection.execute(
        """
        CREATE TABLE ip_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK (type IN ('VM', 'OS', 'BMC', 'VIP', 'OTHER')),
            project_id INTEGER REFERENCES projects(id),
            host_id INTEGER REFERENCES hosts(id),
            notes TEXT,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO ip_assets (
            id,
            ip_address,
            type,
            project_id,
            host_id,
            notes,
            archived,
            created_at,
            updated_at
        )
        SELECT
            id,
            ip_address,
            type,
            project_id,
            {select_host_id},
            {select_notes},
            {select_archived},
            {select_created_at},
            {select_updated_at}
        FROM ip_assets_old
        """
    )
    connection.execute("DROP TABLE ip_assets_old")
