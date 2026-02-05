import sqlite3

from app.db import init_db
from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    create_host,
    create_ip_asset,
    create_project,
    get_host_by_name,
    get_ip_asset_by_ip,
    delete_ip_asset,
    get_ip_asset_metrics,
    list_hosts,
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


def test_create_bmc_without_host_creates_server_host_and_links_asset(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.10",
        asset_type=IPAssetType.BMC,
        auto_host_for_bmc=True,
    )

    host = get_host_by_name(connection, "server_192.168.12.10")
    assert host is not None
    assert asset.host_id == host.id


def test_create_bmc_reuses_existing_server_host(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    existing_host = create_host(connection, name="server_192.168.12.11")

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.11",
        asset_type=IPAssetType.BMC,
        auto_host_for_bmc=True,
    )

    hosts = list_hosts(connection)
    assert len([host for host in hosts if host.name == "server_192.168.12.11"]) == 1
    assert asset.host_id == existing_host.id


def test_create_bmc_with_explicit_host_id_does_not_autocreate(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    provided_host = create_host(connection, name="provided-host")

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.12",
        asset_type=IPAssetType.BMC,
        host_id=provided_host.id,
        auto_host_for_bmc=True,
    )

    assert get_host_by_name(connection, "server_192.168.12.12") is None
    assert asset.host_id == provided_host.id


def test_create_non_bmc_without_host_does_not_autocreate(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.13",
        asset_type=IPAssetType.OS,
        auto_host_for_bmc=True,
    )

    assert get_host_by_name(connection, "server_192.168.12.13") is None
    assert asset.host_id is None


def test_delete_ip_asset_removes_record(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    create_ip_asset(connection, ip_address="10.0.2.10", asset_type=IPAssetType.VM)

    deleted = delete_ip_asset(connection, "10.0.2.10")

    assert deleted is True
    assert get_ip_asset_by_ip(connection, "10.0.2.10") is None


def test_delete_ip_asset_returns_false_for_unknown_ip(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    deleted = delete_ip_asset(connection, "10.0.2.99")

    assert deleted is False
