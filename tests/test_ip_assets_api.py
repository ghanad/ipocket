from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, repository
from app.main import app
from app.models import UserRole


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with TestClient(app) as test_client:
        yield test_client, db_path
    auth.clear_tokens()


def _create_user(db_path, username: str, password: str, role: UserRole) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_user(
            connection,
            username=username,
            hashed_password=auth.hash_password(password),
            role=role,
        )
    finally:
        connection.close()


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_ipasset_crud_without_owner(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    project_response = test_client.post("/projects", headers=headers, json={"name": "Core"})
    project_id = project_response.json()["id"]

    create = test_client.post(
        "/ip-assets",
        headers=headers,
        json={
            "ip_address": "10.10.0.10",
            "type": "VM",
            "project_id": project_id,
        },
    )
    assert create.status_code == 200
    assert "owner_id" not in create.json()

    update_project = test_client.post("/projects", headers=headers, json={"name": "Edge"})
    edge_id = update_project.json()["id"]
    update = test_client.patch(
        "/ip-assets/10.10.0.10",
        headers=headers,
        json={"project_id": edge_id},
    )
    assert update.status_code == 200
    assert update.json()["project_id"] == edge_id


def test_create_bmc_ip_asset_auto_creates_host_by_default(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    response = test_client.post(
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


def test_auto_host_creation_can_be_disabled_via_env(client, monkeypatch) -> None:
    test_client, db_path = client
    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "0")
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    response = test_client.post(
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


def test_delete_ip_asset_endpoint(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    create = test_client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.10.0.99", "type": "VM"},
    )
    assert create.status_code == 200

    delete_response = test_client.request("DELETE", "/ip-assets/10.10.0.99", headers=headers)
    assert delete_response.status_code == 204

    get_deleted = test_client.get("/ip-assets/10.10.0.99")
    assert get_deleted.status_code == 404


def test_delete_ip_asset_endpoint_returns_404_for_missing_ip(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    delete_response = test_client.request("DELETE", "/ip-assets/10.10.0.250", headers=headers)
    assert delete_response.status_code == 404
