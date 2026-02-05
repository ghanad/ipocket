import sqlite3

from app.db import init_db
from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    create_ip_asset,
    create_project,
    get_ip_asset_by_ip,
    get_ip_asset_metrics,
)


def _setup_connection(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    return connection


def test_create_project_and_ipasset(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Core")
    asset = create_ip_asset(
        connection,
        ip_address="10.0.0.10",
        subnet="10.0.0.0/24",
        gateway="10.0.0.1",
        asset_type=IPAssetType.VM,
        project_id=project.id,
    )
    fetched = get_ip_asset_by_ip(connection, "10.0.0.10")
    assert fetched is not None
    assert fetched.ip_address == asset.ip_address
    assert fetched.project_id == project.id


def test_get_ip_asset_metrics_counts(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Apps")
    create_ip_asset(connection, "10.0.1.1", IPAssetType.VM, project_id=project.id)
    create_ip_asset(connection, "10.0.1.2", IPAssetType.OS, project_id=None)
    create_ip_asset(connection, "10.0.1.3", IPAssetType.VIP, project_id=None)
    create_ip_asset(connection, "10.0.1.4", IPAssetType.OTHER, project_id=project.id)
    archive_ip_asset(connection, "10.0.1.4")

    metrics = get_ip_asset_metrics(connection)
    assert metrics["total"] == 4
    assert metrics["archived_total"] == 1
    assert metrics["unassigned_project_total"] == 2
