import sqlite3

from app import db


def test_init_db_runs_alembic_migrations(tmp_path) -> None:
    db_path = tmp_path / "migrations.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        db.init_db(connection)
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "alembic_version" in tables
        assert "ip_assets" in tables
        assert "hosts" in tables
        assert "audit_logs" in tables
        assert "ip_ranges" in tables
        assert "tags" in tables
        assert "ip_asset_tags" in tables
    finally:
        connection.close()


def test_ip_assets_table_excludes_subnet_and_gateway(tmp_path) -> None:
    db_path = tmp_path / "schema.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        db.init_db(connection)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(ip_assets)").fetchall()}
        assert "subnet" not in columns
        assert "gateway" not in columns
    finally:
        connection.close()
