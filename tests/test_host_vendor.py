from __future__ import annotations

import sqlite3

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


def test_create_host_with_vendor_persists(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    response = test_client.post(
        "/hosts",
        headers=headers,
        json={"name": "host-a", "vendor": "HPE", "notes": "rack-a"},
    )

    assert response.status_code == 200
    assert response.json()["vendor"] == "HPE"

    connection = db.connect(str(db_path))
    try:
        host = repository.get_host_by_name(connection, "host-a")
        assert host is not None
        assert host.vendor == "HPE"
    finally:
        connection.close()


def test_update_host_vendor(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    created = test_client.post("/hosts", headers=headers, json={"name": "host-b"})
    host_id = created.json()["id"]

    updated = test_client.patch(
        f"/hosts/{host_id}",
        headers=headers,
        json={"vendor": "Dell"},
    )

    assert updated.status_code == 200
    assert updated.json()["vendor"] == "Dell"


def test_ui_host_detail_renders_vendor(client) -> None:
    test_client, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="host-c", vendor="Lenovo")
    finally:
        connection.close()

    response = test_client.get(f"/ui/hosts/{host.id}")

    assert response.status_code == 200
    assert "Vendor:" in response.text
    assert "Lenovo" in response.text


def test_init_db_migrates_host_vendor_column_idempotent(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('Viewer', 'Editor', 'Admin')),
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE ip_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL UNIQUE,
                subnet TEXT NOT NULL,
                gateway TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('VM', 'OS', 'BMC', 'VIP', 'OTHER')),
                project_id INTEGER,
                notes TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )
        connection.commit()

        db.init_db(connection)
        db.init_db(connection)

        host_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(hosts)").fetchall()
        }
        assert "vendor" in host_columns
    finally:
        connection.close()
