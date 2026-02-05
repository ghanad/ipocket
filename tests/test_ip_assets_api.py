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
            "subnet": "10.10.0.0/24",
            "gateway": "10.10.0.1",
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
