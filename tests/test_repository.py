import sqlite3

import pytest

from app.db import init_db
from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    create_ip_asset,
    create_owner,
    create_project,
    get_ip_asset_by_ip,
    get_ip_asset_metrics,
    list_active_ip_assets,
)


def _setup_connection(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    return connection


def test_create_project_owner_and_ipasset(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    project = create_project(connection, name="Core", description="Core services")
    owner = create_owner(connection, name="Network Team", contact="netops@example.com")

    asset = create_ip_asset(
        connection,
        ip_address="10.0.0.10",
        subnet="10.0.0.0/24",
        gateway="10.0.0.1",
        asset_type=IPAssetType.VM,
        project_id=project.id,
        owner_id=owner.id,
        notes="Primary app",
    )

    fetched = get_ip_asset_by_ip(connection, "10.0.0.10")
    assert fetched is not None
    assert fetched.ip_address == asset.ip_address
    assert fetched.project_id == project.id
    assert fetched.owner_id == owner.id
    assert fetched.archived is False


def test_ip_address_unique_constraint(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    create_ip_asset(
        connection,
        ip_address="10.0.0.11",
        subnet="10.0.0.0/24",
        gateway="10.0.0.1",
        asset_type=IPAssetType.PHYSICAL,
    )

    with pytest.raises(sqlite3.IntegrityError):
        create_ip_asset(
            connection,
            ip_address="10.0.0.11",
            subnet="10.0.0.0/24",
            gateway="10.0.0.1",
            asset_type=IPAssetType.PHYSICAL,
        )


def test_archive_excludes_from_active_list(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    create_ip_asset(
        connection,
        ip_address="10.0.0.12",
        subnet="10.0.0.0/24",
        gateway="10.0.0.1",
        asset_type=IPAssetType.VIP,
    )

    archive_ip_asset(connection, "10.0.0.12")

    active_assets = list_active_ip_assets(connection)
    assert active_assets == []


def test_get_ip_asset_metrics_counts(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    project = create_project(connection, name="Apps")
    owner = create_owner(connection, name="Infra")

    create_ip_asset(
        connection,
        ip_address="10.0.1.1",
        subnet="10.0.1.0/24",
        gateway="10.0.1.1",
        asset_type=IPAssetType.VM,
        project_id=project.id,
        owner_id=owner.id,
    )
    create_ip_asset(
        connection,
        ip_address="10.0.1.2",
        subnet="10.0.1.0/24",
        gateway="10.0.1.1",
        asset_type=IPAssetType.PHYSICAL,
        project_id=project.id,
        owner_id=None,
    )
    create_ip_asset(
        connection,
        ip_address="10.0.1.3",
        subnet="10.0.1.0/24",
        gateway="10.0.1.1",
        asset_type=IPAssetType.VIP,
        project_id=None,
        owner_id=None,
    )
    create_ip_asset(
        connection,
        ip_address="10.0.1.4",
        subnet="10.0.1.0/24",
        gateway="10.0.1.1",
        asset_type=IPAssetType.OTHER,
        project_id=project.id,
        owner_id=owner.id,
    )
    archive_ip_asset(connection, "10.0.1.4")

    metrics = get_ip_asset_metrics(connection)
    assert metrics["total"] == 4
    assert metrics["archived_total"] == 1
    assert metrics["unassigned_owner_total"] == 2
    assert metrics["unassigned_project_total"] == 1
    assert metrics["unassigned_both_total"] == 1
