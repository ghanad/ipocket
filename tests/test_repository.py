import sqlite3

import pytest

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
    delete_host,
    get_ip_asset_metrics,
    list_hosts,
    list_hosts_with_ip_counts,
    update_project,
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
    project = create_project(connection, name="Core", color="#223344")
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
    assert project.color == "#223344"


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


def test_update_project_color(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Edge")

    updated = update_project(connection, project.id, color="#112233")

    assert updated is not None
    assert updated.color == "#112233"


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


def test_delete_host_removes_record_when_unlinked(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    host = create_host(connection, name="host-delete-1")

    deleted = delete_host(connection, host.id)

    assert deleted is True
    assert get_host_by_name(connection, "host-delete-1") is None


def test_delete_host_raises_for_linked_ip_assets(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    host = create_host(connection, name="host-delete-2")
    create_ip_asset(connection, ip_address="10.0.3.10", asset_type=IPAssetType.OS, host_id=host.id)

    with pytest.raises(sqlite3.IntegrityError):
        delete_host(connection, host.id)


def test_delete_host_returns_false_for_unknown_host(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    deleted = delete_host(connection, 9999)

    assert deleted is False


def test_list_hosts_with_ip_counts_includes_os_and_bmc_ips(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    host = create_host(connection, name="host-ips")
    create_ip_asset(connection, ip_address="10.20.0.10", asset_type=IPAssetType.OS, host_id=host.id)
    create_ip_asset(connection, ip_address="10.20.0.11", asset_type=IPAssetType.OS, host_id=host.id)
    create_ip_asset(connection, ip_address="10.20.0.20", asset_type=IPAssetType.BMC, host_id=host.id)
    create_ip_asset(connection, ip_address="10.20.0.30", asset_type=IPAssetType.VM, host_id=host.id)

    hosts = list_hosts_with_ip_counts(connection)

    assert len(hosts) == 1
    assert hosts[0]["os_ips"] == "10.20.0.10, 10.20.0.11"
    assert hosts[0]["bmc_ips"] == "10.20.0.20"
