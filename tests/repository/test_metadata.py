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

        repository.set_ip_asset_archived(
            connection, archived_asset.ip_address, archived=True
        )

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


def test_list_vendor_ip_counts_returns_active_counts(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        vendor_a = repository.create_vendor(connection, name="Dell")
        vendor_b = repository.create_vendor(connection, name="Cisco")
        host_a = repository.create_host(connection, name="node-a", vendor=vendor_a.name)
        host_b = repository.create_host(connection, name="node-b", vendor=vendor_b.name)
        repository.create_host(connection, name="node-novendor")

        repository.create_ip_asset(
            connection,
            ip_address="10.0.2.10",
            asset_type=IPAssetType.VM,
            host_id=host_a.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.2.11",
            asset_type=IPAssetType.BMC,
            host_id=host_a.id,
        )
        archived = repository.create_ip_asset(
            connection,
            ip_address="10.0.2.12",
            asset_type=IPAssetType.OS,
            host_id=host_b.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.2.13",
            asset_type=IPAssetType.OTHER,
        )
        repository.set_ip_asset_archived(connection, archived.ip_address, archived=True)

        counts = repository.list_vendor_ip_counts(connection)

        assert counts == {vendor_a.id: 2}
    finally:
        connection.close()


def test_project_metadata_supports_sqlalchemy_session(
    _setup_connection, _setup_session
) -> None:
    session = _setup_session()
    try:
        created = repository.create_project(
            session,
            name="Session Project",
            description="Via ORM session",
            color="#123abc",
        )
        assert created.color == "#123abc"

        updated = repository.update_project(
            session,
            project_id=created.id,
            name="Session Project Updated",
            description="Updated",
            color="#456def",
        )
        assert updated is not None
        assert updated.name == "Session Project Updated"
        assert updated.color == "#456def"

        connection = _setup_connection()
        try:
            repository.create_ip_asset(
                connection,
                ip_address="10.9.0.10",
                asset_type=IPAssetType.VM,
                project_id=created.id,
            )
        finally:
            connection.close()

        counts = repository.list_project_ip_counts(session)
        assert counts[created.id] == 1
    finally:
        session.close()


def test_tag_metadata_supports_sqlalchemy_session(
    _setup_connection, _setup_session
) -> None:
    session = _setup_session()
    try:
        tag = repository.create_tag(session, name="orm-tag", color="#abc123")
        assert tag.color == "#abc123"

        connection = _setup_connection()
        try:
            asset = repository.create_ip_asset(
                connection,
                ip_address="10.9.1.10",
                asset_type=IPAssetType.OTHER,
            )
            repository.set_ip_asset_tags(connection, asset.id, ["orm-tag"])
        finally:
            connection.close()

        counts = repository.list_tag_ip_counts(session)
        assert counts[tag.id] == 1
    finally:
        session.close()
