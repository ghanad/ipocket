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


def test_create_host_with_vendor_catalog_selection(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    vendor_response = test_client.post("/vendors", headers=headers, json={"name": "HPE"})
    assert vendor_response.status_code == 200

    response = test_client.post(
        "/hosts",
        headers=headers,
        json={"name": "host-a", "vendor_id": vendor_response.json()["id"], "notes": "rack-a"},
    )

    assert response.status_code == 200
    assert response.json()["vendor"] == "HPE"


def test_update_host_vendor_by_vendor_id(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")
    headers = {"Authorization": f"Bearer {token}"}

    dell = test_client.post("/vendors", headers=headers, json={"name": "Dell"})
    created = test_client.post("/hosts", headers=headers, json={"name": "host-b"})
    host_id = created.json()["id"]

    updated = test_client.patch(
        f"/hosts/{host_id}",
        headers=headers,
        json={"vendor_id": dell.json()["id"]},
    )

    assert updated.status_code == 200
    assert updated.json()["vendor"] == "Dell"



def test_hosts_ui_form_uses_vendor_dropdown(client) -> None:
    test_client, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_vendor(connection, "HPE")
    finally:
        connection.close()

    response = test_client.get("/ui/hosts")
    assert response.status_code == 200
    assert 'name="vendor_id"' in response.text
    assert "HPE" in response.text

def test_vendors_ui_page_renders_and_is_editable(client) -> None:
    from app.models import User
    from app.routes import ui

    test_client, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        vendor = repository.create_vendor(connection, "Lenovo")
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)

    try:
        list_response = test_client.get("/ui/vendors")
        assert list_response.status_code == 200
        assert "Lenovo" in list_response.text

        edit_response = test_client.post(f"/ui/vendors/{vendor.id}/edit", data={"name": "Supermicro"}, follow_redirects=False)
        assert edit_response.status_code == 303

        after = test_client.get("/ui/vendors")
        assert "Supermicro" in after.text
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
        app.dependency_overrides.pop(ui.require_ui_editor, None)


def test_init_db_migrates_host_vendor_text_to_vendor_catalog(tmp_path) -> None:
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
                vendor TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("INSERT INTO hosts (name, notes, vendor) VALUES ('host-legacy', 'x', 'Cisco')")
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

        host_columns = {row["name"] for row in connection.execute("PRAGMA table_info(hosts)").fetchall()}
        assert "vendor_id" in host_columns

        vendor_names = [row["name"] for row in connection.execute("SELECT name FROM vendors").fetchall()]
        assert "Cisco" in vendor_names

        host = repository.get_host_by_name(connection, "host-legacy")
        assert host is not None
        assert host.vendor == "Cisco"
    finally:
        connection.close()
