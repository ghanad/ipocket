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


def _create_ip_asset(db_path, ip_address: str) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            subnet="10.0.0.0/24",
            gateway="10.0.0.1",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()


def test_login_happy_path(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)

    response = test_client.post(
        "/login", json={"username": "viewer", "password": "viewer-pass"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_auth_required_for_write_endpoints(client) -> None:
    test_client, _db_path = client

    response = test_client.post(
        "/ip-assets",
        json={
            "ip_address": "10.0.0.30",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )

    assert response.status_code == 401


def test_viewer_cannot_write(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    _create_ip_asset(db_path, "10.0.0.33")
    token = _login(test_client, "viewer", "viewer-pass")

    response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.31",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )

    assert response.status_code == 403

    update_response = test_client.patch(
        "/ip-assets/10.0.0.33",
        headers=_auth_header(token),
        json={"notes": "blocked"},
    )
    assert update_response.status_code == 403

    archive_response = test_client.post(
        "/ip-assets/10.0.0.33/archive", headers=_auth_header(token)
    )
    assert archive_response.status_code == 403


def test_editor_can_create_update_and_archive(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    create_response = test_client.post(
        "/ip-assets",
        headers=_auth_header(token),
        json={
            "ip_address": "10.0.0.32",
            "subnet": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "type": IPAssetType.VM.value,
        },
    )
    assert create_response.status_code == 200

    update_response = test_client.patch(
        "/ip-assets/10.0.0.32",
        headers=_auth_header(token),
        json={"notes": "Updated", "type": IPAssetType.VIP.value},
    )
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Updated"

    archive_response = test_client.post(
        "/ip-assets/10.0.0.32/archive", headers=_auth_header(token)
    )
    assert archive_response.status_code == 204
