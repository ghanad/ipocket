from __future__ import annotations

from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    bulk_update_ip_assets,
    count_active_ip_assets,
    create_host,
    create_ip_asset,
    create_project,
    delete_ip_asset,
    get_host_by_name,
    get_ip_asset_by_ip,
    get_ip_asset_metrics,
    list_active_ip_assets_paginated,
    list_hosts,
    list_tags_for_ip_assets,
    update_ip_asset,
)


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
    row = connection.execute(
        "SELECT ip_int FROM ip_assets WHERE ip_address = ?",
        (asset.ip_address,),
    ).fetchone()
    assert row is not None
    assert int(row["ip_int"]) == 167772170


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


def test_bulk_update_ip_assets_supports_removing_common_tags(_setup_connection) -> None:
    connection = _setup_connection()
    asset_one = create_ip_asset(
        connection,
        ip_address="10.30.0.21",
        asset_type=IPAssetType.VM,
        tags=["prod", "edge", "ops"],
    )
    asset_two = create_ip_asset(
        connection,
        ip_address="10.30.0.22",
        asset_type=IPAssetType.OS,
        tags=["prod", "edge"],
    )

    updated_assets = bulk_update_ip_assets(
        connection,
        [asset_one.id, asset_two.id],
        tags_to_add=["db"],
        tags_to_remove=["prod"],
    )

    assert len(updated_assets) == 2
    tag_map = list_tags_for_ip_assets(connection, [asset_one.id, asset_two.id])
    assert tag_map[asset_one.id] == ["db", "edge", "ops"]
    assert tag_map[asset_two.id] == ["db", "edge"]


def test_create_bmc_without_host_creates_server_host_and_links_asset(
    _setup_connection,
) -> None:
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


def test_create_bmc_with_explicit_host_id_does_not_autocreate(
    _setup_connection,
) -> None:
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


def test_create_ip_asset_restores_archived_asset_with_same_ip(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    original = create_ip_asset(
        connection,
        ip_address="10.0.9.10",
        asset_type=IPAssetType.VM,
        notes="old",
    )
    archive_ip_asset(connection, original.ip_address)

    restored = create_ip_asset(
        connection,
        ip_address="10.0.9.10",
        asset_type=IPAssetType.OS,
        notes="new",
        tags=["restored"],
    )

    assert restored.id == original.id
    assert restored.archived is False
    assert restored.asset_type == IPAssetType.OS
    assert restored.notes == "new"
    assert list_tags_for_ip_assets(connection, [restored.id])[restored.id] == [
        "restored"
    ]


def test_list_active_ip_assets_paginated_with_search(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(
        connection,
        ip_address="10.60.0.10",
        asset_type=IPAssetType.VM,
        notes="db-primary",
    )
    create_ip_asset(
        connection, ip_address="10.60.0.11", asset_type=IPAssetType.VM, notes="web-tier"
    )

    total = count_active_ip_assets(connection, query_text="db")
    assets = list_active_ip_assets_paginated(
        connection, query_text="db", limit=10, offset=0
    )

    assert total == 1
    assert len(assets) == 1
    assert assets[0].ip_address == "10.60.0.10"


def test_list_active_ip_assets_paginated_sorts_ip_addresses_numerically(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="192.168.1.2", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="192.168.1.11", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="192.168.1.1", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(
        connection, query_text="192.168.1.", limit=10, offset=0
    )

    assert [asset.ip_address for asset in assets] == [
        "192.168.1.1",
        "192.168.1.2",
        "192.168.1.11",
    ]


def test_list_active_ip_assets_paginated_applies_offset_after_numeric_sort(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    for ip_address in ["192.168.1.2", "192.168.1.11", "192.168.1.1"]:
        create_ip_asset(connection, ip_address=ip_address, asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(
        connection, query_text="192.168.1.", limit=1, offset=1
    )

    assert [asset.ip_address for asset in assets] == ["192.168.1.2"]


def test_list_active_ip_assets_paginated_sorts_zero_padded_ipv4_numerically(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.40.0.10", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.40.0.00", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.40.0.02", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(
        connection, query_text="10.40.0.", limit=10, offset=0
    )

    assert [asset.ip_address for asset in assets] == [
        "10.40.0.00",
        "10.40.0.02",
        "10.40.0.10",
    ]


def test_list_active_ip_assets_paginated_sorts_ipv6_and_fallback_deterministically(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="2001:db8::10", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="2001:db8::2", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="not-an-ip", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(connection, limit=10, offset=0)

    assert [asset.ip_address for asset in assets] == [
        "2001:db8::10",
        "2001:db8::2",
        "not-an-ip",
    ]


def test_list_active_ip_assets_paginated_returns_empty_for_out_of_range_page(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.62.0.10", asset_type=IPAssetType.VM)
    create_ip_asset(connection, ip_address="10.62.0.11", asset_type=IPAssetType.VM)

    assets = list_active_ip_assets_paginated(connection, limit=2, offset=4)

    assert assets == []


def test_list_active_ip_assets_paginated_applies_filters_before_limit_and_offset(
    _setup_connection,
) -> None:
    connection = _setup_connection()
    create_ip_asset(
        connection,
        ip_address="10.63.0.10",
        asset_type=IPAssetType.VM,
        notes="db-primary",
    )
    create_ip_asset(
        connection,
        ip_address="10.63.0.11",
        asset_type=IPAssetType.VM,
        notes="db-replica",
    )
    create_ip_asset(
        connection,
        ip_address="10.63.0.12",
        asset_type=IPAssetType.VM,
        notes="web-tier",
    )

    assets = list_active_ip_assets_paginated(
        connection,
        query_text="db",
        limit=1,
        offset=1,
    )

    assert [asset.ip_address for asset in assets] == ["10.63.0.11"]


def test_list_active_ip_assets_paginated_with_tag_filter_any(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(
        connection, ip_address="10.61.0.10", asset_type=IPAssetType.VM, tags=["edge"]
    )
    create_ip_asset(
        connection, ip_address="10.61.0.11", asset_type=IPAssetType.VM, tags=["db"]
    )
    create_ip_asset(
        connection, ip_address="10.61.0.12", asset_type=IPAssetType.VM, tags=["ops"]
    )

    total = count_active_ip_assets(connection, tag_names=["edge", "db"])
    assets = list_active_ip_assets_paginated(
        connection, tag_names=["edge", "db"], limit=10, offset=0
    )

    assert total == 2
    assert len(assets) == 2
    assert [asset.ip_address for asset in assets] == ["10.61.0.10", "10.61.0.11"]


def test_tag_filter_is_case_insensitive_for_count_and_list(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(
        connection, ip_address="10.61.1.10", asset_type=IPAssetType.VM, tags=["Prod"]
    )
    create_ip_asset(
        connection, ip_address="10.61.1.11", asset_type=IPAssetType.VM, tags=["edge"]
    )

    total = count_active_ip_assets(connection, tag_names=["PROD"])
    assets = list_active_ip_assets_paginated(
        connection, tag_names=["PROD"], limit=10, offset=0
    )

    assert total == 1
    assert [asset.ip_address for asset in assets] == ["10.61.1.10"]


def test_count_ip_assets_with_archived_only_filter(_setup_connection) -> None:
    connection = _setup_connection()
    create_ip_asset(connection, ip_address="10.70.0.10", asset_type=IPAssetType.VM)
    archived_asset = create_ip_asset(
        connection, ip_address="10.70.0.11", asset_type=IPAssetType.OS
    )
    archive_ip_asset(connection, archived_asset.ip_address)

    total_archived = count_active_ip_assets(connection, archived_only=True)
    archived_assets = list_active_ip_assets_paginated(
        connection, archived_only=True, limit=10, offset=0
    )

    assert total_archived == 1
    assert len(archived_assets) == 1
    assert archived_assets[0].ip_address == "10.70.0.11"


def test_list_ip_assets_with_project_unassigned_only_filter(_setup_connection) -> None:
    connection = _setup_connection()
    project = create_project(connection, name="Core")
    create_ip_asset(
        connection,
        ip_address="10.71.0.10",
        asset_type=IPAssetType.VM,
        project_id=project.id,
    )
    create_ip_asset(connection, ip_address="10.71.0.11", asset_type=IPAssetType.OS)

    total_unassigned = count_active_ip_assets(connection, project_unassigned_only=True)
    unassigned_assets = list_active_ip_assets_paginated(
        connection,
        project_unassigned_only=True,
        limit=10,
        offset=0,
    )

    assert total_unassigned == 1
    assert len(unassigned_assets) == 1
    assert unassigned_assets[0].ip_address == "10.71.0.11"
