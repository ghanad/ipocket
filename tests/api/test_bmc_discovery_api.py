from __future__ import annotations

from unittest.mock import patch
from fastapi.testclient import TestClient

from app import repository
from app.models import IPAssetType, UserRole


def test_bmc_discovery_targets_api(
    client: TestClient, _create_user, _login, _auth_headers, _setup_connection
):
    _create_user("editor_user", "password123", UserRole.EDITOR)
    token = _login("editor_user", "password123")
    headers = _auth_headers(token)

    conn = _setup_connection()
    try:
        host = repository.create_host(conn, name="srv-api-target", vendor=None)
        repository.create_ip_asset(
            conn,
            ip_address="192.168.10.10",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        conn.close()

    # Unauthorized
    resp = client.get("/api/hosts/bmc-discovery/targets")
    assert resp.status_code == 401

    # Authorized
    resp = client.get("/api/hosts/bmc-discovery/targets", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    target = next(t for t in data["targets"] if t["host_id"] == host.id)
    assert target["host_name"] == "srv-api-target"
    assert target["bmc_assets"][0]["ip_address"] == "192.168.10.10"


@patch("app.services.bmc_discovery.probe_bmc_tls")
def test_bmc_discovery_scan_api(
    mock_probe,
    client: TestClient,
    _create_user,
    _login,
    _auth_headers,
    _setup_connection,
):
    _create_user("editor_user", "password123", UserRole.EDITOR)
    token = _login("editor_user", "password123")
    headers = _auth_headers(token)

    mock_probe.return_value = {
        "status": "matched",
        "detected_vendor": "Dell",
        "confidence": "high",
        "fingerprint_summary": "Dell Inc.",
        "error": None,
    }

    conn = _setup_connection()
    try:
        host = repository.create_host(conn, name="srv-scan-test", vendor=None)
        repository.create_ip_asset(
            conn,
            ip_address="192.168.10.20",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        conn.close()

    payload = {"host_ids": [host.id], "timeout": 1.0, "concurrency": 2}
    resp = client.post("/api/hosts/bmc-discovery/scan", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["matched_count"] == 1
    assert data["results"][0]["detected_vendor"] == "Dell"
    assert data["results"][0]["status"] == "matched"


def test_bmc_discovery_apply_api(
    client: TestClient, _create_user, _login, _auth_headers, _setup_connection
):
    _create_user("editor_user", "password123", UserRole.EDITOR)
    _create_user("viewer_user", "password123", UserRole.VIEWER)

    editor_token = _login("editor_user", "password123")
    viewer_token = _login("viewer_user", "password123")

    conn = _setup_connection()
    try:
        host = repository.create_host(conn, name="srv-apply-api", vendor=None)
    finally:
        conn.close()

    apply_payload = {"items": [{"host_id": host.id, "vendor_name": "HPE"}]}

    # Viewer should be forbidden
    resp = client.post(
        "/api/hosts/bmc-discovery/apply",
        json=apply_payload,
        headers=_auth_headers(viewer_token),
    )
    assert resp.status_code == 403

    # Editor should succeed
    resp = client.post(
        "/api/hosts/bmc-discovery/apply",
        json=apply_payload,
        headers=_auth_headers(editor_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["applied"][0]["vendor_name"] == "HPE"

    # Verify in DB
    conn = _setup_connection()
    try:
        updated = repository.get_host_by_id(conn, host.id)
        assert updated.vendor == "HPE"
    finally:
        conn.close()
