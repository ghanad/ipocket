from __future__ import annotations

from app import repository
from app.models import IPAssetType


def test_delete_project_unassigns_linked_ip_assets(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        project = repository.create_project(connection, name="Core")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.0.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )

        deleted = repository.delete_project(connection, project.id)

        assert deleted is True
        assert repository.get_project_by_id(connection, project.id) is None
        updated_asset = repository.get_ip_asset_by_id(connection, asset.id)
        assert updated_asset is not None
        assert updated_asset.project_id is None
    finally:
        connection.close()


def test_list_project_ip_counts_returns_active_counts(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        project_a = repository.create_project(connection, name="Project A")
        project_b = repository.create_project(connection, name="Project B")

        repository.create_ip_asset(
            connection,
            ip_address="10.0.1.10",
            asset_type=IPAssetType.VM,
            project_id=project_a.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.1.11",
            asset_type=IPAssetType.VM,
            project_id=project_a.id,
        )
        archived_asset = repository.create_ip_asset(
            connection,
            ip_address="10.0.1.12",
            asset_type=IPAssetType.VM,
            project_id=project_b.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.1.13",
            asset_type=IPAssetType.VM,
        )

        repository.set_ip_asset_archived(connection, archived_asset.ip_address, archived=True)

        counts = repository.list_project_ip_counts(connection)

        assert counts == {project_a.id: 2}
    finally:
        connection.close()


def test_delete_vendor_unassigns_linked_hosts(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        vendor = repository.create_vendor(connection, name="Dell")
        host = repository.create_host(connection, name="node-01", vendor="Dell")

        deleted = repository.delete_vendor(connection, vendor.id)

        assert deleted is True
        assert repository.get_vendor_by_id(connection, vendor.id) is None
        updated_host = repository.get_host_by_id(connection, host.id)
        assert updated_host is not None
        assert updated_host.vendor is None
    finally:
        connection.close()
