from __future__ import annotations

from app import repository
from app.models import IPAssetType


def test_management_overview_returns_summary_and_utilization(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        project = repository.create_project(connection, name="Apps")
        vendor = repository.create_vendor(connection, name="Lenovo")
        host = repository.create_host(connection, name="edge-01", vendor=vendor.name)
        repository.create_ip_asset(
            connection,
            ip_address="10.50.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
        )
        archived_asset = repository.create_ip_asset(
            connection, ip_address="10.50.0.11", asset_type=IPAssetType.OS
        )
        repository.archive_ip_asset(connection, archived_asset.ip_address)
        repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
        repository.create_ip_asset(
            connection, ip_address="192.168.10.10", asset_type=IPAssetType.VM
        )
        repository.create_ip_asset(
            connection, ip_address="192.168.10.11", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    response = client.get("/api/management/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "active_ip_total": 3,
        "archived_ip_total": 1,
        "host_total": 1,
        "vendor_total": 1,
        "project_total": 1,
    }
    assert payload["utilization"] == [
        {
            "id": 1,
            "name": "Corp LAN",
            "cidr": "192.168.10.0/24",
            "total_usable": 254,
            "used": 2,
            "free": 252,
            "utilization_percent": 2 / 254 * 100,
        }
    ]


def test_management_overview_returns_empty_defaults(client) -> None:
    response = client.get("/api/management/overview")

    assert response.status_code == 200
    assert response.json() == {
        "summary": {
            "active_ip_total": 0,
            "archived_ip_total": 0,
            "host_total": 0,
            "vendor_total": 0,
            "project_total": 0,
        },
        "utilization": [],
    }
