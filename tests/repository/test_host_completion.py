from __future__ import annotations

from app import repository
from app.models import IPAssetType


def test_list_host_completion_records_classifies_active_pairs(_setup_connection):
    connection = _setup_connection()
    try:
        project = repository.create_project(connection, "payments")
        repository.create_vendor(connection, "Dell")

        complete = repository.create_host(connection, "complete", vendor="Dell")
        repository.create_ip_asset(
            connection,
            "10.10.0.1",
            IPAssetType.OS,
            project_id=project.id,
            host_id=complete.id,
        )
        repository.create_ip_asset(
            connection, "10.20.0.1", IPAssetType.BMC, host_id=complete.id
        )

        os_only = repository.create_host(connection, "os-only")
        repository.create_ip_asset(
            connection, "10.10.0.2", IPAssetType.OS, host_id=os_only.id
        )
        archived_bmc = repository.create_ip_asset(
            connection, "10.20.0.2", IPAssetType.BMC, host_id=os_only.id
        )
        repository.set_ip_asset_archived(connection, archived_bmc.ip_address, True)

        bmc_only = repository.create_host(connection, "bmc-only")
        repository.create_ip_asset(
            connection, "10.20.0.3", IPAssetType.BMC, host_id=bmc_only.id
        )
        repository.create_host(connection, "empty")

        complete_records = repository.list_host_completion_records(
            connection, kind="complete", limit=10
        )
        incomplete_records = repository.list_host_completion_records(
            connection, kind="incomplete", limit=10
        )
    finally:
        connection.close()

    assert [record["host_id"] for record in complete_records] == [complete.id]
    assert complete_records[0]["vendor"] == "Dell"
    assert complete_records[0]["os_assets"] == [
        {
            "id": complete_records[0]["os_assets"][0]["id"],
            "ip_address": "10.10.0.1",
            "project_id": project.id,
            "project_name": "payments",
        }
    ]
    assert [record["host_id"] for record in incomplete_records] == [
        os_only.id,
        bmc_only.id,
    ]
    assert incomplete_records[0]["bmc_assets"] == []
    assert incomplete_records[1]["os_assets"] == []


def test_list_host_completion_records_filters_missing_type_and_cursor(
    _setup_connection,
):
    connection = _setup_connection()
    try:
        first = repository.create_host(connection, "first")
        second = repository.create_host(connection, "second")
        repository.create_ip_asset(
            connection, "10.11.0.1", IPAssetType.OS, host_id=first.id
        )
        repository.create_ip_asset(
            connection, "10.21.0.2", IPAssetType.BMC, host_id=second.id
        )

        missing_bmc = repository.list_host_completion_records(
            connection,
            kind="incomplete",
            missing_type=IPAssetType.BMC,
            limit=10,
        )
        after_first = repository.list_host_completion_records(
            connection,
            kind="incomplete",
            limit=10,
            after_host_id=first.id,
        )
    finally:
        connection.close()

    assert [record["host_id"] for record in missing_bmc] == [first.id]
    assert [record["host_id"] for record in after_first] == [second.id]
