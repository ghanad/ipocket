from __future__ import annotations

import sqlite3

from app import db, repository
from app.main import app
from app.models import User, UserRole
from app.routes import ui


def test_create_host_with_vendor_catalog_selection(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    vendor_response = client.post("/vendors", headers=headers, json={"name": "HPE"})
    assert vendor_response.status_code == 200

    response = client.post(
        "/hosts",
        headers=headers,
        json={"name": "host-a", "vendor_id": vendor_response.json()["id"], "notes": "rack-a"},
    )

    assert response.status_code == 200
    assert response.json()["vendor"] == "HPE"


def test_update_host_vendor_by_vendor_id(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    dell = client.post("/vendors", headers=headers, json={"name": "Dell"})
    created = client.post("/hosts", headers=headers, json={"name": "host-b"})
    host_id = created.json()["id"]

    updated = client.patch(f"/hosts/{host_id}", headers=headers, json={"vendor_id": dell.json()["id"]})

    assert updated.status_code == 200
    assert updated.json()["vendor"] == "Dell"


def test_hosts_ui_form_uses_vendor_dropdown(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        repository.create_vendor(connection, "HPE")
    finally:
        connection.close()

    response = client.get("/ui/hosts")
    assert response.status_code == 200
    assert 'name="vendor_id"' in response.text
    assert "HPE" in response.text


def test_vendors_ui_page_uses_drawer_actions(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        vendor = repository.create_vendor(connection, "Lenovo")
    finally:
        connection.close()

    response = client.get("/ui/vendors")

    assert response.status_code == 200
    assert "data-vendor-add" in response.text
    assert "data-vendor-create-drawer" in response.text
    assert "data-vendor-edit-drawer" in response.text
    assert "data-vendor-delete-drawer" in response.text
    assert f'data-vendor-edit="{vendor.id}"' in response.text
    assert f'data-vendor-delete="{vendor.id}"' in response.text


def test_vendors_ui_edit_and_delete_flow(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        vendor = repository.create_vendor(connection, "Lenovo")
        host = repository.create_host(connection, name="node-1", vendor="Lenovo")
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)

    try:
        edit_redirect = client.get(f"/ui/vendors/{vendor.id}/edit", follow_redirects=False)
        assert edit_redirect.status_code == 303
        assert edit_redirect.headers["location"].endswith(f"/ui/vendors?edit={vendor.id}")

        edit_response = client.post(
            f"/ui/vendors/{vendor.id}/edit",
            data={"name": "Supermicro"},
            follow_redirects=False,
        )
        assert edit_response.status_code == 303

        delete_redirect = client.get(f"/ui/vendors/{vendor.id}/delete", follow_redirects=False)
        assert delete_redirect.status_code == 303
        assert delete_redirect.headers["location"].endswith(f"/ui/vendors?delete={vendor.id}")

        delete_error = client.post(
            f"/ui/vendors/{vendor.id}/delete",
            data={"confirm_name": "Wrong"},
        )
        assert delete_error.status_code == 400
        assert "Vendor name confirmation does not match." in delete_error.text
        assert 'data-vendor-delete-open="true"' in delete_error.text

        delete_response = client.post(
            f"/ui/vendors/{vendor.id}/delete",
            data={"confirm_name": "Supermicro"},
            follow_redirects=False,
        )
        assert delete_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    connection = _setup_connection()
    try:
        assert repository.get_vendor_by_id(connection, vendor.id) is None
        updated_host = repository.get_host_by_id(connection, host.id)
        assert updated_host is not None
        assert updated_host.vendor is None
    finally:
        connection.close()


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
