from __future__ import annotations


from app.models import IPAssetType, UserRole
from app.repository import (
    archive_ip_asset,
    count_audit_logs,
    create_host,
    create_ip_asset,
    create_project,
    create_user,
    create_vendor,
    delete_ip_asset,
    get_audit_logs_for_ip,
    get_management_summary,
    list_audit_logs,
    list_audit_logs_paginated,
    update_ip_asset,
    update_project,
)


def test_audit_logs_record_ip_asset_changes(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )
    project = create_project(connection, name="Core")
    host = create_host(connection, name="node-01")

    asset = create_ip_asset(
        connection,
        ip_address="10.10.10.10",
        asset_type=IPAssetType.VM,
        current_user=user,
    )
    update_ip_asset(
        connection,
        ip_address="10.10.10.10",
        project_id=project.id,
        host_id=host.id,
        notes="updated",
        current_user=user,
    )
    delete_ip_asset(connection, "10.10.10.10", current_user=user)

    logs = get_audit_logs_for_ip(connection, asset.id)

    assert [log.action for log in logs] == ["DELETE", "UPDATE", "CREATE"]
    assert all(log.username == "auditor" for log in logs)
    assert any("project: Unassigned -> Core" in (log.changes or "") for log in logs)
    assert any("host: Unassigned -> node-01" in (log.changes or "") for log in logs)
    assert any("notes:" in (log.changes or "") for log in logs)


def test_update_ip_asset_clears_notes_and_logs_change(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )
    asset = create_ip_asset(
        connection,
        ip_address="10.10.30.10",
        asset_type=IPAssetType.VM,
        notes="initial note",
        current_user=user,
    )

    updated = update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        notes=None,
        current_user=user,
        notes_provided=True,
    )

    assert updated is not None
    assert updated.notes is None
    logs = get_audit_logs_for_ip(connection, asset.id)
    assert logs[0].action == "UPDATE"
    assert "notes: initial note -> " in (logs[0].changes or "")


def test_update_ip_asset_no_changes_skips_audit_log(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )
    project = create_project(connection, name="Core")
    host = create_host(connection, name="node-01")

    asset = create_ip_asset(
        connection,
        ip_address="10.10.40.10",
        asset_type=IPAssetType.VM,
        project_id=project.id,
        host_id=host.id,
        notes="steady",
        tags=["core", "edge"],
        current_user=user,
    )

    updated = update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=asset.asset_type,
        project_id=project.id,
        host_id=host.id,
        notes="steady",
        tags=["core", "edge"],
        current_user=user,
        notes_provided=True,
    )

    assert updated is not None
    logs = get_audit_logs_for_ip(connection, asset.id)
    assert len(logs) == 1
    assert logs[0].action == "CREATE"


def test_update_ip_asset_tag_change_logs_update(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )

    asset = create_ip_asset(
        connection,
        ip_address="10.10.50.10",
        asset_type=IPAssetType.VM,
        tags=["core"],
        current_user=user,
    )

    updated = update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        tags=["core", "edge"],
        current_user=user,
    )

    assert updated is not None
    logs = get_audit_logs_for_ip(connection, asset.id)
    assert logs[0].action == "UPDATE"
    assert "tags: core -> core, edge" in (logs[0].changes or "")


def test_list_audit_logs_returns_recent_ip_entries(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )

    create_ip_asset(
        connection,
        ip_address="10.10.20.1",
        asset_type=IPAssetType.VM,
        current_user=user,
    )
    create_ip_asset(
        connection,
        ip_address="10.10.20.2",
        asset_type=IPAssetType.OS,
        current_user=user,
    )

    logs = list_audit_logs(connection, limit=10)

    assert len(logs) >= 2
    assert logs[0].target_label == "10.10.20.2"
    assert logs[0].action == "CREATE"
    assert logs[1].target_label == "10.10.20.1"


def test_count_audit_logs_returns_total(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )

    initial_count = count_audit_logs(connection)
    assert initial_count == 0

    create_ip_asset(
        connection,
        ip_address="10.10.30.1",
        asset_type=IPAssetType.VM,
        current_user=user,
    )
    create_ip_asset(
        connection,
        ip_address="10.10.30.2",
        asset_type=IPAssetType.OS,
        current_user=user,
    )

    new_count = count_audit_logs(connection)
    assert new_count == 2


def test_list_audit_logs_paginated_returns_correct_page(_setup_connection) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )

    for i in range(5):
        create_ip_asset(
            connection,
            ip_address=f"10.10.40.{i}",
            asset_type=IPAssetType.VM,
            current_user=user,
        )

    total = count_audit_logs(connection)
    assert total == 5

    first_page = list_audit_logs_paginated(connection, limit=2, offset=0)
    assert len(first_page) == 2
    assert first_page[0].target_label == "10.10.40.4"
    assert first_page[1].target_label == "10.10.40.3"

    second_page = list_audit_logs_paginated(connection, limit=2, offset=2)
    assert len(second_page) == 2
    assert second_page[0].target_label == "10.10.40.2"
    assert second_page[1].target_label == "10.10.40.1"

    third_page = list_audit_logs_paginated(connection, limit=2, offset=4)
    assert len(third_page) == 1
    assert third_page[0].target_label == "10.10.40.0"


def test_list_audit_logs_paginated_empty_when_offset_exceeds_total(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    user = create_user(
        connection, username="auditor", hashed_password="x", role=UserRole.ADMIN
    )

    create_ip_asset(
        connection,
        ip_address="10.10.50.1",
        asset_type=IPAssetType.VM,
        current_user=user,
    )

    logs = list_audit_logs_paginated(connection, limit=10, offset=100)
    assert len(logs) == 0


def test_get_management_summary_counts(_setup_connection) -> None:
    connection = _setup_connection()
    project = create_project(connection, name="Infra")
    vendor = create_vendor(connection, name="Dell")
    host = create_host(connection, name="edge-01", vendor=vendor.name)
    create_ip_asset(
        connection, "10.10.0.1", IPAssetType.VM, project_id=project.id, host_id=host.id
    )
    archived_asset = create_ip_asset(connection, "10.10.0.2", IPAssetType.OS)
    archive_ip_asset(connection, archived_asset.ip_address)

    summary = get_management_summary(connection)

    assert summary["active_ip_total"] == 1
    assert summary["archived_ip_total"] == 1
    assert summary["host_total"] == 1
    assert summary["vendor_total"] == 1
    assert summary["project_total"] == 1


def test_update_project_color(_setup_connection) -> None:
    connection = _setup_connection()
    project = create_project(connection, name="Edge")

    updated = update_project(connection, project.id, color="#112233")

    assert updated is not None
    assert updated.color == "#112233"
