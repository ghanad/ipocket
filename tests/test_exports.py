from __future__ import annotations

import csv
import io
from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient

from app import auth, db, repository
from app.main import app
from app.models import IPAssetType, UserRole
from app.routes import ui


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with TestClient(app) as test_client:
        yield test_client, db_path
    auth.clear_tokens()


def _create_user(db_path, username: str, password: str) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_user(
            connection,
            username=username,
            hashed_password=auth.hash_password(password),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()


def _login_ui(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/ui/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303
    cookie_header = response.headers.get("set-cookie")
    if cookie_header:
        jar = SimpleCookie()
        jar.load(cookie_header)
        if ui.SESSION_COOKIE in jar:
            return jar[ui.SESSION_COOKIE].value
    raise AssertionError("Session cookie not set after login.")


def _auth_headers(session_cookie: str) -> dict[str, str]:
    return {"Cookie": f"{ui.SESSION_COOKIE}={session_cookie}"}


def _seed_export_data(db_path) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        vendor = repository.create_vendor(connection, "Dell")
        project = repository.create_project(connection, "core", "Core systems")
        host = repository.create_host(connection, name="node-01", notes="primary", vendor=vendor.name)
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.10",
            subnet="10.0.0.0/24",
            gateway="10.0.0.1",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
            notes="active asset",
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.99",
            subnet="10.0.0.0/24",
            gateway="10.0.0.1",
            asset_type=IPAssetType.VIP,
            project_id=project.id,
            host_id=host.id,
            notes="archived asset",
        )
        repository.archive_ip_asset(connection, "10.0.0.99")
    finally:
        connection.close()


def _parse_csv_rows(payload: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(payload))
    return list(reader)


def test_export_content_types_and_archived_filter(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "exporter", "export-pass")
    _seed_export_data(db_path)
    session_cookie = _login_ui(test_client, "exporter", "export-pass")

    response = test_client.get("/export/ip-assets.csv", headers=_auth_headers(session_cookie))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    ip_rows = _parse_csv_rows(response.text)
    assert {row["ip_address"] for row in ip_rows} == {"10.0.0.10"}

    response = test_client.get(
        "/export/ip-assets.csv?include_archived=1",
        headers=_auth_headers(session_cookie),
    )
    ip_rows = _parse_csv_rows(response.text)
    assert {row["ip_address"] for row in ip_rows} == {"10.0.0.10", "10.0.0.99"}

    json_endpoints = [
        "/export/ip-assets.json",
        "/export/hosts.json",
        "/export/vendors.json",
        "/export/projects.json",
        "/export/bundle.json",
    ]
    for endpoint in json_endpoints:
        json_response = test_client.get(endpoint, headers=_auth_headers(session_cookie))
        assert json_response.status_code == 200
        assert json_response.headers["content-type"].startswith("application/json")

    csv_endpoints = [
        "/export/hosts.csv",
        "/export/vendors.csv",
        "/export/projects.csv",
    ]
    for endpoint in csv_endpoints:
        csv_response = test_client.get(endpoint, headers=_auth_headers(session_cookie))
        assert csv_response.status_code == 200
        assert csv_response.headers["content-type"].startswith("text/csv")


def test_bundle_json_schema(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "bundle-user", "bundle-pass")
    _seed_export_data(db_path)
    session_cookie = _login_ui(test_client, "bundle-user", "bundle-pass")

    response = test_client.get("/export/bundle.json", headers=_auth_headers(session_cookie))
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1"
    assert payload["app"] == "ipocket"
    data = payload["data"]
    assert set(data.keys()) == {"vendors", "projects", "hosts", "ip_assets"}


def test_ui_export_page_has_bundle_link(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "ui-user", "ui-pass")
    session_cookie = _login_ui(test_client, "ui-user", "ui-pass")

    response = test_client.get("/ui/export", headers=_auth_headers(session_cookie))
    assert response.status_code == 200
    assert "/export/bundle.json" in response.text
