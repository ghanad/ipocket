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

        tag_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tags)").fetchall()
        }
        assert "color" in tag_columns
    finally:
        connection.close()


def test_ip_assets_table_excludes_subnet_and_gateway(tmp_path) -> None:
    db_path = tmp_path / "schema.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        db.init_db(connection)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(ip_assets)").fetchall()
        }
        assert "subnet" not in columns
        assert "gateway" not in columns
    finally:
        connection.close()


def test_listing_indexes_exist_after_migrations(tmp_path) -> None:
    db_path = tmp_path / "indexes.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        db.init_db(connection)
        connection.close()
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row

        ip_assets_indexes = {
            row["name"]
            for row in connection.execute("PRAGMA index_list('ip_assets')").fetchall()
        }
        assert "ix_ip_assets_archived_project_type" in ip_assets_indexes
        assert "ix_ip_assets_archived_ip_address" in ip_assets_indexes

        ip_asset_tags_indexes = {
            row["name"]
            for row in connection.execute(
                "PRAGMA index_list('ip_asset_tags')"
            ).fetchall()
        }
        assert "ix_ip_asset_tags_tag_id_ip_asset_id" in ip_asset_tags_indexes

        tags_indexes = {
            row["name"]
            for row in connection.execute("PRAGMA index_list('tags')").fetchall()
        }
        assert "ix_tags_name_lower" in tags_indexes
    finally:
        connection.close()
