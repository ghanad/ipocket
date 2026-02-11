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
