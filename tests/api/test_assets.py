from __future__ import annotations

import warnings

from pydantic.warnings import UnsupportedFieldAttributeWarning

from app import db, repository
from app.models import UserRole


def test_ipasset_crud_without_owner(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    project_response = client.post("/projects", headers=headers, json={"name": "Core"})
    project_id = project_response.json()["id"]

    create = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.10.0.10", "type": "VM", "project_id": project_id},
    )
    assert create.status_code == 200
    assert "owner_id" not in create.json()

    edge_id = client.post("/projects", headers=headers, json={"name": "Edge"}).json()["id"]
    update = client.patch("/ip-assets/10.10.0.10", headers=headers, json={"project_id": edge_id})
    assert update.status_code == 200
    assert update.json()["project_id"] == edge_id


def test_create_bmc_ip_asset_auto_creates_host_by_default(client, db_path, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    response = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "192.168.50.10", "type": "BMC"},
    )
    assert response.status_code == 200

    connection = db.connect(str(db_path))
    try:
        host = repository.get_host_by_name(connection, "server_192.168.50.10")
        assert host is not None
        assert response.json()["host_id"] == host.id
    finally:
        connection.close()


def test_auto_host_creation_can_be_disabled_via_env(
    client,
    db_path,
    monkeypatch,
    _create_user,
    _login,
    _auth_headers,
) -> None:
    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "0")
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    response = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "192.168.50.11", "type": "BMC"},
    )
    assert response.status_code == 200
    assert response.json()["host_id"] is None

    connection = db.connect(str(db_path))
    try:
        assert repository.get_host_by_name(connection, "server_192.168.50.11") is None
    finally:
        connection.close()


def test_delete_ip_asset_endpoint(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    create = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.10.0.99", "type": "VM"},
    )
    assert create.status_code == 200

    assert client.request("DELETE", "/ip-assets/10.10.0.99", headers=headers).status_code == 204
    assert client.get("/ip-assets/10.10.0.99").status_code == 404


def test_delete_ip_asset_endpoint_returns_404_for_missing_ip(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    delete_response = client.request("DELETE", "/ip-assets/10.10.0.250", headers=headers)
    assert delete_response.status_code == 404


def test_create_ip_asset_has_no_pydantic_alias_warning(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))
    project_id = client.post("/projects", headers=headers, json={"name": "Core"}).json()["id"]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", UnsupportedFieldAttributeWarning)
        response = client.post(
            "/ip-assets",
            headers=headers,
            json={"ip_address": "10.10.0.11", "type": "VM", "project_id": project_id},
        )

    assert response.status_code == 200
    alias_warnings = [w for w in caught if issubclass(w.category, UnsupportedFieldAttributeWarning)]
    assert alias_warnings == []
