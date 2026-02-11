from __future__ import annotations


import pytest

from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    create_host,
    create_ip_asset,
    create_ip_range,
    create_project,
    delete_ip_range,
    get_ip_range_address_breakdown,
    get_ip_range_by_id,
    get_ip_range_utilization,
    update_ip_range,
)


def test_create_ip_range_valid_and_invalid(_setup_connection) -> None:
    connection = _setup_connection()

    ip_range = create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24", notes="main")

    assert ip_range.cidr == "192.168.10.0/24"
    assert ip_range.name == "Corp LAN"

    with pytest.raises(ValueError):
        create_ip_range(connection, name="Bad range", cidr="192.168.10.999/24")

def test_update_and_delete_ip_range(_setup_connection) -> None:
    connection = _setup_connection()

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

def test_ip_range_utilization_counts(_setup_connection) -> None:
    connection = _setup_connection()
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

def test_ip_range_address_breakdown(_setup_connection) -> None:
    connection = _setup_connection()
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

