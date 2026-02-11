from __future__ import annotations

from app import repository
from app.models import IPAssetType, UserRole


def _editor_headers(_create_user, _login, _auth_headers) -> dict[str, str]:
    _create_user("editor-extra", "editor-pass", UserRole.EDITOR)
    return _auth_headers(_login("editor-extra", "editor-pass"))


def test_list_hosts_endpoint_returns_payload_shape(
    client, _setup_connection, _create_user, _login, _auth_headers
) -> None:
    connection = _setup_connection()
    try:
        repository.create_vendor(connection, "Dell")
        repository.create_host(
            connection, name="edge-01", notes="rack-a", vendor="Dell"
        )
    finally:
        connection.close()

    headers = _editor_headers(_create_user, _login, _auth_headers)
    response = client.get("/hosts", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "edge-01"
    assert payload[0]["notes"] == "rack-a"
    assert payload[0]["vendor"] == "Dell"


def test_get_host_returns_linked_assets_grouped(
    client, _setup_connection, _create_user, _login, _auth_headers
) -> None:
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, name="edge-02")
        repository.create_ip_asset(
            connection,
            ip_address="10.80.0.10",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.80.0.11",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.80.0.12",
            asset_type=IPAssetType.VM,
            host_id=host.id,
        )
    finally:
        connection.close()

    headers = _editor_headers(_create_user, _login, _auth_headers)
    response = client.get(f"/hosts/{host.id}", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "edge-02"
    assert [asset["type"] for asset in payload["linked_assets"]["os"]] == ["OS"]
    assert [asset["type"] for asset in payload["linked_assets"]["bmc"]] == ["BMC"]
    assert [asset["type"] for asset in payload["linked_assets"]["other"]] == ["VM"]


def test_get_host_returns_404_for_missing_host(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)
    response = client.get("/hosts/9999", headers=headers)
    assert response.status_code == 404


def test_create_and_update_host_validate_vendor_and_missing_host(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)

    create_invalid_vendor = client.post(
        "/hosts",
        headers=headers,
        json={"name": "host-x", "vendor_id": 9999},
    )
    assert create_invalid_vendor.status_code == 422
    assert create_invalid_vendor.json()["detail"] == "Selected vendor does not exist."

    created = client.post("/hosts", headers=headers, json={"name": "host-y"})
    assert created.status_code == 200
    host_id = created.json()["id"]

    update_invalid_vendor = client.patch(
        f"/hosts/{host_id}",
        headers=headers,
        json={"vendor_id": 9999},
    )
    assert update_invalid_vendor.status_code == 422
    assert update_invalid_vendor.json()["detail"] == "Selected vendor does not exist."

    update_missing_host = client.patch(
        "/hosts/9999",
        headers=headers,
        json={"name": "ghost"},
    )
    assert update_missing_host.status_code == 404
