from __future__ import annotations

from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    count_hosts,
    create_host,
    create_ip_asset,
    create_project,
    create_tag,
    create_vendor,
    delete_host,
    get_host_by_name,
    get_ip_asset_by_ip,
    list_host_pair_ips_for_hosts,
    list_hosts_with_ip_counts,
    list_hosts_with_ip_counts_paginated,
)


def test_delete_host_removes_record_when_unlinked(_setup_connection) -> None:
    connection = _setup_connection()
    host = create_host(connection, name="host-delete-1")

    deleted = delete_host(connection, host.id)

    assert deleted is True
    assert get_host_by_name(connection, "host-delete-1") is None


def test_delete_host_unlinks_linked_ip_assets_before_delete(_setup_connection) -> None:
    connection = _setup_connection()
    host = create_host(connection, name="host-delete-2")
    create_ip_asset(
        connection, ip_address="10.0.3.10", asset_type=IPAssetType.OS, host_id=host.id
    )
    create_ip_asset(
        connection, ip_address="10.0.3.11", asset_type=IPAssetType.BMC, host_id=host.id
    )

    deleted = delete_host(connection, host.id)
    os_asset = get_ip_asset_by_ip(connection, "10.0.3.10")
    bmc_asset = get_ip_asset_by_ip(connection, "10.0.3.11")

    assert deleted is True
    assert get_host_by_name(connection, "host-delete-2") is None
    assert os_asset is not None
    assert bmc_asset is not None
    assert os_asset.host_id is None
    assert bmc_asset.host_id is None


def test_delete_host_returns_false_for_unknown_host(_setup_connection) -> None:
    connection = _setup_connection()

    deleted = delete_host(connection, 9999)

    assert deleted is False


def test_list_hosts_with_ip_counts_includes_os_and_bmc_ips(_setup_connection) -> None:
    connection = _setup_connection()
    host = create_host(connection, name="host-ips")
    project = create_project(connection, name="Edge", color="#1d4ed8")
    os_asset_a = create_ip_asset(
        connection,
        ip_address="10.20.0.10",
        asset_type=IPAssetType.OS,
        host_id=host.id,
        project_id=project.id,
    )
    os_asset_b = create_ip_asset(
        connection,
        ip_address="10.20.0.11",
        asset_type=IPAssetType.OS,
        host_id=host.id,
        project_id=project.id,
    )
    bmc_asset = create_ip_asset(
        connection,
        ip_address="10.20.0.20",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
        project_id=project.id,
    )
    create_ip_asset(
        connection, ip_address="10.20.0.30", asset_type=IPAssetType.VM, host_id=host.id
    )

    hosts = list_hosts_with_ip_counts(connection)

    assert len(hosts) == 1
    assert hosts[0]["os_ips"] == "10.20.0.10, 10.20.0.11"
    assert hosts[0]["bmc_ips"] == "10.20.0.20"
    assert hosts[0]["os_ip_links"] == [
        {"id": os_asset_a.id, "ip_address": "10.20.0.10"},
        {"id": os_asset_b.id, "ip_address": "10.20.0.11"},
    ]
    assert hosts[0]["bmc_ip_links"] == [
        {"id": bmc_asset.id, "ip_address": "10.20.0.20"}
    ]
    assert hosts[0]["project_count"] == 1
    assert hosts[0]["project_name"] == "Edge"
    assert hosts[0]["project_color"] == "#1d4ed8"


def test_list_hosts_with_ip_counts_includes_linked_active_ip_tags(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    host = create_host(connection, name="host-tags")
    create_tag(connection, name="prod", color="#22c55e")
    create_tag(connection, name="linux", color="#38bdf8")
    create_ip_asset(
        connection,
        ip_address="10.21.0.10",
        asset_type=IPAssetType.OS,
        host_id=host.id,
        tags=["prod", "linux"],
    )
    create_ip_asset(
        connection,
        ip_address="10.21.0.11",
        asset_type=IPAssetType.BMC,
        host_id=host.id,
        tags=["prod"],
    )
    archived_asset = create_ip_asset(
        connection,
        ip_address="10.21.0.12",
        asset_type=IPAssetType.VM,
        host_id=host.id,
        tags=["retired"],
    )
    archive_ip_asset(connection, archived_asset.ip_address)

    hosts = list_hosts_with_ip_counts(connection)

    assert hosts[0]["ip_tags"] == [
        {"name": "linux", "color": "#38bdf8"},
        {"name": "prod", "color": "#22c55e"},
    ]


def test_list_host_pair_ips_for_hosts_maps_os_and_bmc(_setup_connection) -> None:
    connection = _setup_connection()
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


def test_count_hosts_returns_total(_setup_connection) -> None:
    connection = _setup_connection()
    create_host(connection, name="host-1")
    create_host(connection, name="host-2")
    create_host(connection, name="host-3")

    total = count_hosts(connection)

    assert total == 3


def test_count_hosts_returns_zero_when_empty(_setup_connection) -> None:
    connection = _setup_connection()

    total = count_hosts(connection)

    assert total == 0


def test_list_hosts_with_ip_counts_paginated_returns_subset(_setup_connection) -> None:
    connection = _setup_connection()
    create_host(connection, name="alpha")
    create_host(connection, name="beta")
    create_host(connection, name="gamma")
    create_host(connection, name="delta")

    page1 = list_hosts_with_ip_counts_paginated(connection, limit=2, offset=0)
    page2 = list_hosts_with_ip_counts_paginated(connection, limit=2, offset=2)

    # Results are ordered alphabetically by name
    assert [h["name"] for h in page1] == ["alpha", "beta"]
    assert [h["name"] for h in page2] == ["delta", "gamma"]


def test_list_hosts_with_ip_counts_paginated_respects_offset(_setup_connection) -> None:
    connection = _setup_connection()
    create_host(connection, name="host-a")
    create_host(connection, name="host-b")
    create_host(connection, name="host-c")

    hosts = list_hosts_with_ip_counts_paginated(connection, limit=10, offset=1)

    assert len(hosts) == 2
    assert [h["name"] for h in hosts] == ["host-b", "host-c"]


def test_list_hosts_with_ip_counts_paginated_returns_empty_for_large_offset(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_host(connection, name="solo")

    hosts = list_hosts_with_ip_counts_paginated(connection, limit=10, offset=100)

    assert hosts == []


def test_list_hosts_with_ip_counts_filters_by_project_type_tag_and_status(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    project = create_project(connection, name="Core", color="#2563eb")
    matching = create_host(connection, name="core-host")
    other = create_host(connection, name="edge-host")
    free = create_host(connection, name="free-host")
    create_ip_asset(
        connection,
        ip_address="10.70.0.10",
        asset_type=IPAssetType.OS,
        host_id=matching.id,
        project_id=project.id,
        tags=["prod"],
    )
    create_ip_asset(
        connection,
        ip_address="10.70.0.20",
        asset_type=IPAssetType.BMC,
        host_id=other.id,
        tags=["oob"],
    )

    hosts = list_hosts_with_ip_counts_paginated(
        connection,
        limit=20,
        offset=0,
        project_id=project.id,
        asset_type=IPAssetType.OS,
        tag_names=["prod"],
        status_filter="linked",
    )
    total = count_hosts(
        connection,
        project_id=project.id,
        asset_type=IPAssetType.OS,
        tag_names=["prod"],
        status_filter="linked",
    )
    free_hosts = list_hosts_with_ip_counts_paginated(
        connection, limit=20, offset=0, status_filter="free"
    )

    assert total == 1
    assert [host["name"] for host in hosts] == ["core-host"]
    assert [host["name"] for host in free_hosts] == [free.name]


def test_list_hosts_with_ip_counts_filters_by_search_vendor_and_unassigned(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    vendor = create_vendor(connection, name="Dell")
    assigned_project = create_project(connection, name="Assigned")
    matching = create_host(connection, name="tag-search-host", vendor=vendor.name)
    assigned = create_host(connection, name="assigned-host", vendor=vendor.name)
    create_ip_asset(
        connection,
        ip_address="10.71.0.10",
        asset_type=IPAssetType.OS,
        host_id=matching.id,
        tags=["prod"],
    )
    create_ip_asset(
        connection,
        ip_address="10.71.0.20",
        asset_type=IPAssetType.OS,
        host_id=assigned.id,
        project_id=assigned_project.id,
        tags=["prod"],
    )

    hosts = list_hosts_with_ip_counts_paginated(
        connection,
        limit=20,
        offset=0,
        query_text="prod",
        vendor_id=vendor.id,
        unassigned_only=True,
    )

    assert [host["name"] for host in hosts] == ["tag-search-host"]
