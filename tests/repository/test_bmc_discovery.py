from __future__ import annotations

from app import repository
from app.models import IPAssetType


def test_get_bmc_discovery_targets(_setup_connection):
    conn = _setup_connection()
    try:
        # Create a host without vendor
        host1 = repository.create_host(conn, name="srv-no-vendor", vendor=None)
        # Create a host with vendor
        repository.create_vendor(conn, "Dell")
        host2 = repository.create_host(conn, name="srv-with-vendor", vendor="Dell")

        # Add BMC IP to host1
        repository.create_ip_asset(
            conn,
            ip_address="10.10.10.50",
            asset_type=IPAssetType.BMC,
            host_id=host1.id,
        )
        # Add OS IP to host1
        repository.create_ip_asset(
            conn,
            ip_address="10.10.10.51",
            asset_type=IPAssetType.OS,
            host_id=host1.id,
        )
        # Add BMC IP to host2
        repository.create_ip_asset(
            conn,
            ip_address="10.10.10.60",
            asset_type=IPAssetType.BMC,
            host_id=host2.id,
        )

        # Query only unassigned (default)
        targets = repository.get_bmc_discovery_targets(conn, only_unassigned=True)
        assert len(targets) == 1
        assert targets[0]["host_id"] == host1.id
        assert targets[0]["host_name"] == "srv-no-vendor"
        assert len(targets[0]["bmc_assets"]) == 1
        assert targets[0]["bmc_assets"][0]["ip_address"] == "10.10.10.50"

        # Query all hosts
        all_targets = repository.get_bmc_discovery_targets(conn, only_unassigned=False)
        assert len(all_targets) == 2

        # Query specific host ID
        specific = repository.get_bmc_discovery_targets(
            conn, host_ids=[host2.id], only_unassigned=False
        )
        assert len(specific) == 1
        assert specific[0]["host_id"] == host2.id
    finally:
        conn.close()
