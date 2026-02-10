from __future__ import annotations

import sqlite3

import pytest

from app.models import IPAssetType, UserRole
from app.repository import (
    archive_ip_asset,
    bulk_update_ip_assets,
    count_active_ip_assets,
    count_audit_logs,
    count_hosts,
    create_host,
    create_ip_asset,
    create_ip_range,
    create_project,
    create_tag,
    create_user,
    create_vendor,
    delete_host,
    delete_ip_asset,
    delete_ip_range,
    delete_tag,
    get_audit_logs_for_ip,
    get_host_by_name,
    get_ip_asset_by_ip,
    get_ip_asset_metrics,
    get_ip_range_address_breakdown,
    get_ip_range_by_id,
    get_ip_range_utilization,
    get_management_summary,
    list_active_ip_assets_paginated,
    list_audit_logs,
    list_audit_logs_paginated,
    list_host_pair_ips_for_hosts,
    list_hosts,
    list_hosts_with_ip_counts,
    list_hosts_with_ip_counts_paginated,
    list_tags,
    list_tags_for_ip_assets,
    update_ip_asset,
    update_ip_range,
    update_project,
    update_tag,
)
from app.utils import normalize_tag_name


def test_create_project_and_ipasset(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_get_ip_asset_metrics_counts(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_create_and_update_ip_asset_tags(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_bulk_update_ip_assets_assigns_type_project_and_tags(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_create_bmc_without_host_creates_server_host_and_links_asset(_setup_connection) -> None:
    connection = _setup_connection()

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.10",
        asset_type=IPAssetType.BMC,
        auto_host_for_bmc=True,
    )

    host = get_host_by_name(connection, "server_192.168.12.10")
    assert host is not None
    assert asset.host_id == host.id

def test_create_bmc_reuses_existing_server_host(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_create_bmc_with_explicit_host_id_does_not_autocreate(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_create_non_bmc_without_host_does_not_autocreate(_setup_connection) -> None:
    connection = _setup_connection()

    asset = create_ip_asset(
        connection,
        ip_address="192.168.12.13",
        asset_type=IPAssetType.OS,
        auto_host_for_bmc=True,
    )

    assert get_host_by_name(connection, "server_192.168.12.13") is None
    assert asset.host_id is None

def test_delete_ip_asset_removes_record(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.0.2.10", asset_type=IPAssetType.VM)

    deleted = delete_ip_asset(connection, "10.0.2.10")

    assert deleted is True
    assert get_ip_asset_by_ip(connection, "10.0.2.10") is None

def test_delete_ip_asset_returns_false_for_unknown_ip(_setup_connection) -> None:
    connection = _setup_connection()

    deleted = delete_ip_asset(connection, "10.0.2.99")

    assert deleted is False

def test_list_active_ip_assets_paginated_with_search(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.60.0.10", asset_type=IPAssetType.VM, notes="db-primary")
    create_ip_asset(connection, ip_address="10.60.0.11", asset_type=IPAssetType.VM, notes="web-tier")

    total = count_active_ip_assets(connection, query_text="db")
    assets = list_active_ip_assets_paginated(connection, query_text="db", limit=10, offset=0)

    assert total == 1
    assert len(assets) == 1
    assert assets[0].ip_address == "10.60.0.10"

def test_list_active_ip_assets_paginated_sorts_ip_addresses_numerically(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="192.168.1.2", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="192.168.1.11", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="192.168.1.1", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(connection, query_text="192.168.1.", limit=10, offset=0)

    assert [asset.ip_address for asset in assets] == ["192.168.1.1", "192.168.1.2", "192.168.1.11"]

def test_list_active_ip_assets_paginated_applies_offset_after_numeric_sort(_setup_connection) -> None:
    connection = _setup_connection()
    for ip_address in ["192.168.1.2", "192.168.1.11", "192.168.1.1"]:
        create_ip_asset(connection, ip_address=ip_address, asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(connection, query_text="192.168.1.", limit=1, offset=1)

    assert [asset.ip_address for asset in assets] == ["192.168.1.2"]

def test_list_active_ip_assets_paginated_sorts_zero_padded_ipv4_numerically(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.40.0.10", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.40.0.00", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.40.0.02", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(connection, query_text="10.40.0.", limit=10, offset=0)

    assert [asset.ip_address for asset in assets] == ["10.40.0.00", "10.40.0.02", "10.40.0.10"]

def test_list_active_ip_assets_paginated_with_tag_filter_any(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.61.0.10", asset_type=IPAssetType.VM, tags=["edge"])
    create_ip_asset(connection, ip_address="10.61.0.11", asset_type=IPAssetType.VM, tags=["db"])
    create_ip_asset(connection, ip_address="10.61.0.12", asset_type=IPAssetType.VM, tags=["ops"])

    total = count_active_ip_assets(connection, tag_names=["edge", "db"])
    assets = list_active_ip_assets_paginated(connection, tag_names=["edge", "db"], limit=10, offset=0)

    assert total == 2
    assert len(assets) == 2
    assert [asset.ip_address for asset in assets] == ["10.61.0.10", "10.61.0.11"]

def test_count_ip_assets_with_archived_only_filter(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.70.0.10", asset_type=IPAssetType.VM)
    archived_asset = create_ip_asset(connection, ip_address="10.70.0.11", asset_type=IPAssetType.OS)
    archive_ip_asset(connection, archived_asset.ip_address)

    total_archived = count_active_ip_assets(connection, archived_only=True)
    archived_assets = list_active_ip_assets_paginated(connection, archived_only=True, limit=10, offset=0)

    assert total_archived == 1
    assert len(archived_assets) == 1
    assert archived_assets[0].ip_address == "10.70.0.11"

