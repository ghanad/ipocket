from __future__ import annotations

import json
from unittest.mock import patch

from app import repository
from app.cli import bmc_discovery as cli_module
from app.models import IPAssetType


@patch("app.services.bmc_discovery.probe_bmc_tls")
def test_bmc_discovery_cli_dry_run_and_json(mock_probe, _setup_connection, capsys):
    mock_probe.return_value = {
        "status": "matched",
        "detected_vendor": "Dell",
        "confidence": "high",
        "fingerprint_summary": "Dell Inc.",
        "error": None,
    }

    conn = _setup_connection()
    try:
        host = repository.create_host(conn, name="srv-cli-test", vendor=None)
        repository.create_ip_asset(
            conn,
            ip_address="192.168.10.99",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        conn.close()

    # Dry-run with JSON output
    exit_code = cli_module.main(["--dry-run", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["total"] >= 1
    assert data["matched"] >= 1
    res = next(r for r in data["results"] if r["host_id"] == host.id)
    assert res["detected_vendor"] == "Dell"

    # Host should NOT be updated in DB because of dry-run
    conn = _setup_connection()
    try:
        current = repository.get_host_by_id(conn, host.id)
        assert current.vendor is None
    finally:
        conn.close()


@patch("app.services.bmc_discovery.probe_bmc_tls")
def test_bmc_discovery_cli_apply(mock_probe, _setup_connection, capsys):
    mock_probe.return_value = {
        "status": "matched",
        "detected_vendor": "HPE",
        "confidence": "high",
        "fingerprint_summary": "Hewlett Packard Enterprise",
        "error": None,
    }

    conn = _setup_connection()
    try:
        host = repository.create_host(conn, name="srv-cli-apply", vendor=None)
        repository.create_ip_asset(
            conn,
            ip_address="192.168.10.98",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        conn.close()

    exit_code = cli_module.main(["--apply", "--host-id", str(host.id)])
    assert exit_code == 0

    # Host SHOULD be updated in DB
    conn = _setup_connection()
    try:
        current = repository.get_host_by_id(conn, host.id)
        assert current.vendor == "HPE"
    finally:
        conn.close()
