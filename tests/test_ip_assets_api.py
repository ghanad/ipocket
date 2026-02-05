from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, repository
from app.main import app
from app.models import IPAssetType, UserRole


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    monkeypatch.delenv("ADMIN_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
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
    response = client.post(
        "/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_ipasset_crud_happy_path(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    project_response = test_client.post(
        "/projects",
        headers=_auth_header(token),
        json={"name": "Core", "description": "Core services"},
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]

    owner_response = test_client.post(
        "/owners",
        headers=_auth_header(token),
        json={"name": "NetOps", "contact": "netops@example.com"},
    )
    assert owner_response.status_code == 200
    owner_id = owner_response.json()["id"]

    list_projects = test_client.get("/projects")
    assert list_projects.status_code == 200
    assert list_projects.json()[0]["id"] == project_id

    list_owners = test_client.get("/owners")
    assert list_owners.status_code == 200
    assert list_owners.json()[0]["id"] == owner_id

    create_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.40",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
            "project_id": project_id,
            "owner_id": owner_id,
            "notes": "App server",
        },
    )
    assert create_response.status_code == 200

    detail_response = test_client.get("/ip-assets/10.0.0.40")
    assert detail_response.status_code == 200
    assert detail_response.json()["owner_id"] == owner_id

    update_response = test_client.patch(
        "/ip-assets/10.0.0.40",
        headers=_auth_header(token),
        json={"notes": "Updated"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Updated"

    list_response = test_client.get("/ip-assets")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    archive_response = test_client.post(
        "/ip-assets/10.0.0.40/archive", headers=_auth_header(token)
    )
    assert archive_response.status_code == 204

    archived_detail = test_client.get("/ip-assets/10.0.0.40")
    assert archived_detail.status_code == 404


def test_unassigned_only_filter(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Platform")
        owner = repository.create_owner(connection, name="Infra")
    finally:
        connection.close()

    assigned_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.41",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
            "project_id": project.id,
            "owner_id": owner.id,
        },
    )
    assert assigned_response.status_code == 200

    unassigned_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.42",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VIP.value,
        },
    )
    assert unassigned_response.status_code == 200

    list_response = test_client.get("/ip-assets?unassigned-only=true")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert [asset["ip_address"] for asset in payload] == ["10.0.0.42"]


def test_invalid_ip_rejected(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "not-an-ip",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid IP address."


def test_create_ip_without_subnet_and_gateway(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.60",
            "type": IPAssetType.OTHER.value,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["subnet"] == ""
    assert payload["gateway"] == ""

def test_unique_ip_constraint_returns_conflict(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.43",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )
    assert response.status_code == 200

    conflict_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.43",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "IP address already exists."


def test_create_ipasset_with_bmc_type(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.70",
            "type": "BMC",
        },
    )

    assert response.status_code == 200
    assert response.json()["type"] == "BMC"


def test_legacy_ipmi_type_is_normalized_to_bmc_on_create_and_update(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    create_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.71",
            "type": "IPMI_ILO",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["type"] == "BMC"

    update_response = test_client.patch(
        "/ip-assets/10.0.0.71",
        headers=_auth_header(token),
        json={"type": "IPMI_iLO"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["type"] == "BMC"
