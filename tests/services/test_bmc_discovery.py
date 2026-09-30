from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from app import repository
from app.models import UserRole
from app.services import bmc_discovery


def test_normalize_vendor_identifies_all_major_vendors():
    # Dell
    assert bmc_discovery.normalize_vendor("CN=idrac-ABC, O=Dell Inc.") == "Dell"
    assert bmc_discovery.normalize_vendor("PowerEdge R740xd") == "Dell"
    assert (
        bmc_discovery.normalize_vendor("Integrated Dell Remote Access Controller")
        == "Dell"
    )

    # HPE
    assert (
        bmc_discovery.normalize_vendor("CN=ILO4-SERVER, O=Hewlett Packard Enterprise")
        == "HPE"
    )
    assert bmc_discovery.normalize_vendor("ProLiant DL380 Gen10") == "HPE"
    assert bmc_discovery.normalize_vendor("Hewlett-Packard Company") == "HPE"

    # Supermicro
    assert bmc_discovery.normalize_vendor("Super Micro Computer, Inc.") == "Supermicro"
    assert bmc_discovery.normalize_vendor("Supermicro IPMI Root CA") == "Supermicro"
    assert bmc_discovery.normalize_vendor("AMI MegaRAC IPMI") == "Supermicro"

    # Cisco
    assert bmc_discovery.normalize_vendor("Cisco Systems CIMC") == "Cisco"
    assert bmc_discovery.normalize_vendor("Cisco UCS C240") == "Cisco"

    # Lenovo
    assert bmc_discovery.normalize_vendor("Lenovo XClarity Controller") == "Lenovo"
    assert bmc_discovery.normalize_vendor("ThinkSystem SR650") == "Lenovo"
    assert (
        bmc_discovery.normalize_vendor("Integrated Management Module 2 IMM2")
        == "Lenovo"
    )

    # Huawei
    assert bmc_discovery.normalize_vendor("Huawei iBMC Controller") == "Huawei"

    # Inspur
    assert bmc_discovery.normalize_vendor("Inspur Electronic Information") == "Inspur"

    # Fujitsu
    assert bmc_discovery.normalize_vendor("Fujitsu PRIMERGY iRMC") == "Fujitsu"

    # Unknown
    assert bmc_discovery.normalize_vendor("Generic Embedded Webserver") is None
    assert bmc_discovery.normalize_vendor("") is None
    assert bmc_discovery.normalize_vendor(None) is None  # type: ignore


def test_extract_der_strings():
    raw_der = b"\x30\x82\x01\x0a\x02\x82\x01\x01\x00Dell Inc.\x00\x00idrac-server-123\x00\x01\x02"
    strings = bmc_discovery.extract_der_strings(raw_der)
    assert any("Dell Inc." in s for s in strings)
    assert any("idrac-server-123" in s for s in strings)


@patch("socket.create_connection")
@patch("ssl.create_default_context")
def test_probe_bmc_tls_matched(mock_ssl_ctx, mock_create_conn):
    mock_sock = MagicMock()
    mock_ssock = MagicMock()
    mock_create_conn.return_value.__enter__.return_value = mock_sock

    mock_ctx_inst = MagicMock()
    mock_ssl_ctx.return_value = mock_ctx_inst
    mock_ctx_inst.wrap_socket.return_value.__enter__.return_value = mock_ssock

    # Mock DER certificate bytes with Dell identifiers
    mock_ssock.getpeercert.return_value = b"\x00Dell Inc.\x00CN=idrac-9ABC\x00"

    result = bmc_discovery.probe_bmc_tls("192.168.1.100", 443, timeout=1.0)
    assert result["status"] == "matched"
    assert result["detected_vendor"] == "Dell"
    assert result["confidence"] == "high"
    assert "Dell" in result["fingerprint_summary"]


@patch("socket.create_connection", side_effect=socket.timeout("Timed out"))
def test_probe_bmc_tls_timeout(mock_create_conn):
    result = bmc_discovery.probe_bmc_tls("192.168.1.101", 443, timeout=0.5)
    assert result["status"] == "timeout"
    assert result["detected_vendor"] is None
    assert "timed out" in result["fingerprint_summary"].lower()


@patch("socket.create_connection", side_effect=ConnectionRefusedError("Refused"))
def test_probe_bmc_tls_connection_refused(mock_create_conn):
    result = bmc_discovery.probe_bmc_tls("192.168.1.102", 443, timeout=0.5)
    assert result["status"] == "unmatched"
    assert result["detected_vendor"] is None
    assert "refused" in result["fingerprint_summary"].lower()


@patch("app.services.bmc_discovery.probe_bmc_tls")
def test_scan_bmc_targets(mock_probe):
    def fake_probe(ip, port, timeout):
        if ip == "10.0.0.1":
            return {
                "status": "matched",
                "detected_vendor": "Dell",
                "confidence": "high",
                "fingerprint_summary": "Dell Inc.",
                "error": None,
            }
        return {
            "status": "unmatched",
            "detected_vendor": None,
            "confidence": None,
            "fingerprint_summary": "Generic Webserver",
            "error": None,
        }

    mock_probe.side_effect = fake_probe

    targets = [
        {
            "host_id": 1,
            "host_name": "srv01",
            "bmc_assets": [{"id": 101, "ip_address": "10.0.0.1"}],
        },
        {
            "host_id": 2,
            "host_name": "srv02",
            "bmc_assets": [{"id": 102, "ip_address": "10.0.0.2"}],
        },
        {
            "host_id": 3,
            "host_name": "srv03",
            "bmc_assets": [],
        },
    ]

    import asyncio

    results = asyncio.run(
        bmc_discovery.scan_bmc_targets(targets, concurrency=5, timeout=1.0)
    )
    assert len(results) == 3

    assert results[0]["host_id"] == 1
    assert results[0]["detected_vendor"] == "Dell"
    assert results[0]["status"] == "matched"

    assert results[1]["host_id"] == 2
    assert results[1]["detected_vendor"] is None
    assert results[1]["status"] == "unmatched"

    assert results[2]["host_id"] == 3
    assert results[2]["error"] == "No BMC IP"


def test_apply_discovered_vendors(_setup_connection):
    db_connection = _setup_connection()
    try:
        # Setup test host and user in DB
        host = repository.create_host(db_connection, name="srv-apply-test", vendor=None)
        user = repository.create_user(
            db_connection,
            username="admin",
            hashed_password="pw",
            role=UserRole.ADMIN,
        )

        items = [{"host_id": host.id, "vendor_name": "Supermicro"}]
        applied = bmc_discovery.apply_discovered_vendors(
            db_connection, items, current_user=user
        )

        assert len(applied) == 1
        assert applied[0]["host_name"] == "srv-apply-test"
        assert applied[0]["vendor_name"] == "Supermicro"

        # Verify host now has Supermicro vendor
        updated_host = repository.get_host_by_id(db_connection, host.id)
        assert updated_host.vendor == "Supermicro"

        # Verify vendor exists in database
        vendor = repository.get_vendor_by_name(db_connection, "Supermicro")
        assert vendor is not None
        assert vendor.name == "Supermicro"

        # Verify audit log was created
        audit_logs = list(repository.list_audit_logs(db_connection, target_type="HOST"))
        assert any("Supermicro" in (log.changes or "") for log in audit_logs)
    finally:
        db_connection.close()
