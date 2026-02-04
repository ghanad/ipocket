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


def test_list_page_renders_seeded_ip(client) -> None:
    test_client, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_ip_asset(
            connection,
            ip_address="10.0.1.10",
            subnet="10.0.1.0/24",
            gateway="10.0.1.1",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    response = test_client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert "10.0.1.10" in response.text
    assert "UNASSIGNED" in response.text


def test_ui_write_requires_editor_role(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    token = _login(test_client, "viewer", "viewer-pass")

    response = test_client.post(
        "/ui/ip-assets/new",
        headers=_auth_header(token),
        data={
            "ip_address": "10.0.2.20",
            "subnet": "10.0.2.0/24",
            "gateway": "10.0.2.1",
            "type": IPAssetType.VM.value,
        },
    )

    assert response.status_code == 403
