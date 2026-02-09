import sqlite3

import pytest

from app.db import init_db
from app.models import IPAssetType, UserRole
from app.repository import (
    archive_ip_asset,
    count_audit_logs,
    create_host,
    create_ip_asset,
    create_ip_range,
    create_project,
    create_user,
    create_vendor,
    get_audit_logs_for_ip,
    get_host_by_name,
    get_ip_asset_by_ip,
    get_management_summary,
    get_ip_range_utilization,
    delete_ip_asset,
    delete_ip_range,
    delete_host,
    get_ip_asset_metrics,
    list_audit_logs,
    list_audit_logs_paginated,
    list_hosts,
    list_hosts_with_ip_counts,
    list_host_pair_ips_for_hosts,
    list_active_ip_assets_paginated,
    count_active_ip_assets,
    bulk_update_ip_assets,
    create_tag,
    delete_tag,
    list_tags_for_ip_assets,
    list_tags,
    update_tag,
    get_ip_range_address_breakdown,
    get_ip_range_by_id,
    update_ip_asset,
    update_ip_range,
    update_project,
)
from app.utils import normalize_tag_name


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


def test_create_and_update_ip_asset_tags(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    asset = create_ip_asset(
        connection,
        ip_address="10.20.0.10",
        asset_type=IPAssetType.VM,
        tags=["Prod", "edge"],
    )
    tag_map = list_tags_for_ip_assets(connection, [asset.id])
    assert tag_map[asset.id] == ["edge", "prod"]

    update_ip_asset(connection, ip_address=asset.ip_address, tags=["core"])
    updated_tags = list_tags_for_ip_assets(connection, [asset.id])
    assert updated_tags[asset.id] == ["core"]


def test_bulk_update_ip_assets_assigns_type_project_and_tags(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Apps")
    asset_one = create_ip_asset(
        connection,
        ip_address="10.30.0.10",
        asset_type=IPAssetType.VM,
        tags=["prod"],
    )
    asset_two = create_ip_asset(
        connection,
        ip_address="10.30.0.11",
        asset_type=IPAssetType.OS,
    )

    updated_assets = bulk_update_ip_assets(
        connection,
        [asset_one.id, asset_two.id],
        asset_type=IPAssetType.VIP,
        project_id=project.id,
        set_project_id=True,
        tags_to_add=["edge", "core"],
    )

    assert len(updated_assets) == 2
    updated_one = get_ip_asset_by_ip(connection, "10.30.0.10")
    updated_two = get_ip_asset_by_ip(connection, "10.30.0.11")
    assert updated_one is not None
    assert updated_two is not None
    assert updated_one.asset_type == IPAssetType.VIP
    assert updated_two.asset_type == IPAssetType.VIP
    assert updated_one.project_id == project.id
    assert updated_two.project_id == project.id

    tag_map = list_tags_for_ip_assets(connection, [asset_one.id, asset_two.id])
    assert tag_map[asset_one.id] == ["core", "edge", "prod"]
    assert tag_map[asset_two.id] == ["core", "edge"]


def test_tag_normalization_rules() -> None:
    assert normalize_tag_name(" Prod ") == "prod"
    with pytest.raises(ValueError):
        normalize_tag_name("bad tag")


def test_create_update_delete_tag(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    tag = create_tag(connection, name="prod", color="#22c55e")
    assert tag.color == "#22c55e"

    updated = update_tag(connection, tag.id, name="prod", color="#0ea5e9")
    assert updated is not None
    assert updated.color == "#0ea5e9"

    tags = list(list_tags(connection))
    assert tags[0].name == "prod"

    deleted = delete_tag(connection, tag.id)
    assert deleted is True


def test_get_management_summary_counts(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Infra")
    vendor = create_vendor(connection, name="Dell")
    host = create_host(connection, name="edge-01", vendor=vendor.name)
    create_ip_asset(connection, "10.10.0.1", IPAssetType.VM, project_id=project.id, host_id=host.id)
    archived_asset = create_ip_asset(connection, "10.10.0.2", IPAssetType.OS)
    archive_ip_asset(connection, archived_asset.ip_address)

    summary = get_management_summary(connection)

    assert summary["active_ip_total"] == 1
    assert summary["archived_ip_total"] == 1
    assert summary["host_total"] == 1
    assert summary["vendor_total"] == 1
    assert summary["project_total"] == 1


def test_update_project_color(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Edge")

    updated = update_project(connection, project.id, color="#112233")

    assert updated is not None
    assert updated.color == "#112233"


def test_create_ip_range_valid_and_invalid(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    ip_range = create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24", notes="main")

    assert ip_range.cidr == "192.168.10.0/24"
    assert ip_range.name == "Corp LAN"

    with pytest.raises(ValueError):
        create_ip_range(connection, name="Bad range", cidr="192.168.10.999/24")


def test_update_and_delete_ip_range(tmp_path) -> None:
    connection = _setup_connection(tmp_path)

    ip_range = create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24", notes="main")

    updated = update_ip_range(
        connection,
        ip_range.id,
        name="Corporate LAN",
        cidr="192.168.20.0/24",
        notes="updated",
    )

    assert updated is not None
    assert updated.name == "Corporate LAN"
    assert updated.cidr == "192.168.20.0/24"
    assert updated.notes == "updated"

    fetched = get_ip_range_by_id(connection, ip_range.id)
    assert fetched is not None
    assert fetched.name == "Corporate LAN"

    assert delete_ip_range(connection, ip_range.id) is True
    assert get_ip_range_by_id(connection, ip_range.id) is None


def test_ip_range_utilization_counts(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
    create_ip_range(connection, name="Point-to-point", cidr="10.0.0.0/31")
    create_ip_range(connection, name="Loopback", cidr="10.0.0.5/32")

    create_ip_asset(connection, ip_address="192.168.10.10", asset_type=IPAssetType.VM)
    archived_asset = create_ip_asset(connection, ip_address="192.168.10.11", asset_type=IPAssetType.OS)
    archive_ip_asset(connection, archived_asset.ip_address)
    create_ip_asset(connection, ip_address="192.168.11.1", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.0.0.0", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.0.0.1", asset_type=IPAssetType.OS)
    create_ip_asset(connection, ip_address="10.0.0.5", asset_type=IPAssetType.VIP)

    utilization = {row["cidr"]: row for row in get_ip_range_utilization(connection)}

    corp = utilization["192.168.10.0/24"]
    assert corp["total_usable"] == 254
    assert corp["used"] == 1
    assert corp["free"] == 253

    p2p = utilization["10.0.0.0/31"]
    assert p2p["total_usable"] == 2
    assert p2p["used"] == 2
    assert p2p["free"] == 0

    loopback = utilization["10.0.0.5/32"]
    assert loopback["total_usable"] == 1
    assert loopback["used"] == 1
    assert loopback["free"] == 0


def test_ip_range_address_breakdown(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    project = create_project(connection, name="Lab")
    host = create_host(connection, name="lab-01")
    ip_range = create_ip_range(connection, name="Lab", cidr="192.168.20.0/30")

    create_ip_asset(
        connection,
        ip_address="192.168.20.1",
        asset_type=IPAssetType.OS,
        project_id=project.id,
        host_id=host.id,
        notes="primary",
    )
    create_ip_asset(
        connection,
        ip_address="192.168.20.3",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
        notes="out-of-band",
    )

    breakdown = get_ip_range_address_breakdown(connection, ip_range.id)

    assert breakdown is not None
    assert breakdown["total_usable"] == 2
    assert breakdown["used"] == 2
    assert breakdown["free"] == 1
    addresses = breakdown["addresses"]
    assert [entry["ip_address"] for entry in addresses] == [
        "192.168.20.1",
        "192.168.20.2",
        "192.168.20.3",
    ]
    assert addresses[0]["status"] == "used"
    assert addresses[0]["project_name"] == "Lab"
    assert addresses[0]["asset_type"] == IPAssetType.OS.value
    assert addresses[0]["host_pair"] == "192.168.20.3"
    assert addresses[0]["notes"] == "primary"
    assert addresses[1]["status"] == "free"
    assert addresses[2]["status"] == "used"
    assert addresses[2]["host_pair"] == "192.168.20.1"


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


def test_list_active_ip_assets_paginated_with_search(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    create_ip_asset(connection, ip_address="10.60.0.10", asset_type=IPAssetType.VM, notes="db-primary")
    create_ip_asset(connection, ip_address="10.60.0.11", asset_type=IPAssetType.VM, notes="web-tier")

    total = count_active_ip_assets(connection, query_text="db")
    assets = list_active_ip_assets_paginated(connection, query_text="db", limit=10, offset=0)

    assert total == 1
    assert len(assets) == 1
    assert assets[0].ip_address == "10.60.0.10"


def test_count_ip_assets_with_archived_only_filter(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    create_ip_asset(connection, ip_address="10.70.0.10", asset_type=IPAssetType.VM)
    archived_asset = create_ip_asset(connection, ip_address="10.70.0.11", asset_type=IPAssetType.OS)
    archive_ip_asset(connection, archived_asset.ip_address)

    total_archived = count_active_ip_assets(connection, archived_only=True)
    archived_assets = list_active_ip_assets_paginated(connection, archived_only=True, limit=10, offset=0)

    assert total_archived == 1
    assert len(archived_assets) == 1
    assert archived_assets[0].ip_address == "10.70.0.11"


def test_list_hosts_with_ip_counts_includes_os_and_bmc_ips(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    host = create_host(connection, name="host-ips")
    project = create_project(connection, name="Edge", color="#1d4ed8")
    create_ip_asset(
        connection,
        ip_address="10.20.0.10",
        asset_type=IPAssetType.OS,
        host_id=host.id,
        project_id=project.id,
    )
    create_ip_asset(
        connection,
        ip_address="10.20.0.11",
        asset_type=IPAssetType.OS,
        host_id=host.id,
        project_id=project.id,
    )
    create_ip_asset(
        connection,
        ip_address="10.20.0.20",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
        project_id=project.id,
    )
    create_ip_asset(connection, ip_address="10.20.0.30", asset_type=IPAssetType.VM, host_id=host.id)

    hosts = list_hosts_with_ip_counts(connection)

    assert len(hosts) == 1
    assert hosts[0]["os_ips"] == "10.20.0.10, 10.20.0.11"
    assert hosts[0]["bmc_ips"] == "10.20.0.20"
    assert hosts[0]["project_count"] == 1
    assert hosts[0]["project_name"] == "Edge"
    assert hosts[0]["project_color"] == "#1d4ed8"


def test_list_host_pair_ips_for_hosts_maps_os_and_bmc(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    host = create_host(connection, name="edge-01")
    other_host = create_host(connection, name="edge-02")
    create_ip_asset(
        connection,
        ip_address="10.50.0.10",
        asset_type=IPAssetType.OS,
        host_id=host.id,
    )
    create_ip_asset(
        connection,
        ip_address="10.50.0.11",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
    )
    archived_asset = create_ip_asset(
        connection,
        ip_address="10.50.0.12",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
    )
    archive_ip_asset(connection, archived_asset.ip_address)
    create_ip_asset(
        connection,
        ip_address="10.50.0.20",
        asset_type=IPAssetType.OS,
        host_id=other_host.id,
    )

    pairs = list_host_pair_ips_for_hosts(connection, [host.id, other_host.id])

    assert pairs[host.id]["OS"] == ["10.50.0.10"]
    assert pairs[host.id]["BMC"] == ["10.50.0.11"]
    assert pairs[other_host.id]["OS"] == ["10.50.0.20"]
    assert pairs[other_host.id]["BMC"] == []


def test_audit_logs_record_ip_asset_changes(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)
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


def test_update_ip_asset_clears_notes_and_logs_change(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)
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


def test_update_ip_asset_no_changes_skips_audit_log(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)
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


def test_update_ip_asset_tag_change_logs_update(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)

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


def test_list_audit_logs_returns_recent_ip_entries(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)

    create_ip_asset(connection, ip_address="10.10.20.1", asset_type=IPAssetType.VM, current_user=user)
    create_ip_asset(connection, ip_address="10.10.20.2", asset_type=IPAssetType.OS, current_user=user)

    logs = list_audit_logs(connection, limit=10)

    assert len(logs) >= 2
    assert logs[0].target_label == "10.10.20.2"
    assert logs[0].action == "CREATE"
    assert logs[1].target_label == "10.10.20.1"


def test_count_audit_logs_returns_total(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)

    initial_count = count_audit_logs(connection)
    assert initial_count == 0

    create_ip_asset(connection, ip_address="10.10.30.1", asset_type=IPAssetType.VM, current_user=user)
    create_ip_asset(connection, ip_address="10.10.30.2", asset_type=IPAssetType.OS, current_user=user)

    new_count = count_audit_logs(connection)
    assert new_count == 2


def test_list_audit_logs_paginated_returns_correct_page(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)

    for i in range(5):
        create_ip_asset(connection, ip_address=f"10.10.40.{i}", asset_type=IPAssetType.VM, current_user=user)

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


def test_list_audit_logs_paginated_empty_when_offset_exceeds_total(tmp_path) -> None:
    connection = _setup_connection(tmp_path)
    user = create_user(connection, username="auditor", hashed_password="x", role=UserRole.ADMIN)

    create_ip_asset(connection, ip_address="10.10.50.1", asset_type=IPAssetType.VM, current_user=user)

    logs = list_audit_logs_paginated(connection, limit=10, offset=100)
    assert len(logs) == 0
