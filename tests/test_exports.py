from __future__ import annotations

import csv
import io
import warnings
from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from app import auth, db, repository
from app.main import app
from app.models import IPAssetType, UserRole
from app.routes import ui


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with FastAPITestClient(app) as test_client:
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


def _login_ui(client: FastAPITestClient, username: str, password: str) -> str:
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
        project = repository.create_project(
            connection, "core", "Core systems", color="#123456"
        )
        host = repository.create_host(
            connection, name="node-01", notes="primary", vendor=vendor.name
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
            notes="active asset",
            tags=["prod", "edge"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.99",
            asset_type=IPAssetType.VIP,
            project_id=project.id,
            host_id=host.id,
            notes="archived asset",
        )
        repository.archive_ip_asset(connection, "10.0.0.99")
    finally:
        connection.close()


def _seed_host_export_pair_data(db_path) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        vendor = repository.create_vendor(connection, "HPE")
        project = repository.create_project(
            connection, "infra", "Infrastructure", color="#334455"
        )
        host = repository.create_host(
            connection, name="node-02", notes="pair host", vendor=vendor.name
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.10.0.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.10.0.11",
            asset_type=IPAssetType.BMC,
            project_id=project.id,
            host_id=host.id,
        )
    finally:
        connection.close()


def _seed_export_order_data_with_null_ip_int(db_path) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        for ip_address in ("10.0.0.10", "10.0.0.2", "10.0.0.1"):
            repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=IPAssetType.VM,
            )
        connection.execute("UPDATE ip_assets SET ip_int = NULL")
        connection.commit()
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

    response = test_client.get(
        "/export/ip-assets.csv", headers=_auth_headers(session_cookie)
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    ip_rows = _parse_csv_rows(response.text)
    assert {row["ip_address"] for row in ip_rows} == {"10.0.0.10"}
    assert ip_rows[0]["tags"] == "edge, prod"

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

    projects_response = test_client.get(
        "/export/projects.csv", headers=_auth_headers(session_cookie)
    )
    project_rows = _parse_csv_rows(projects_response.text)
    assert project_rows == [
        {"name": "core", "description": "Core systems", "color": "#123456"}
    ]


def test_bundle_json_schema(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "bundle-user", "bundle-pass")
    _seed_export_data(db_path)
    session_cookie = _login_ui(test_client, "bundle-user", "bundle-pass")

    response = test_client.get(
        "/export/bundle.json", headers=_auth_headers(session_cookie)
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1"
    assert payload["app"] == "ipocket"
    data = payload["data"]
    assert set(data.keys()) == {"vendors", "projects", "hosts", "ip_assets"}
    assert data["ip_assets"][0]["tags"] == ["edge", "prod"]


def test_ip_assets_csv_export_orders_ips_numerically_when_ip_int_is_null(
    client,
) -> None:
    test_client, db_path = client
    _create_user(db_path, "sort-user", "sort-pass")
    _seed_export_order_data_with_null_ip_int(db_path)
    session_cookie = _login_ui(test_client, "sort-user", "sort-pass")

    response = test_client.get(
        "/export/ip-assets.csv", headers=_auth_headers(session_cookie)
    )
    assert response.status_code == 200

    rows = _parse_csv_rows(response.text)
    assert [row["ip_address"] for row in rows] == [
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.10",
    ]


def test_ui_export_page_has_bundle_link(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "ui-user", "ui-pass")
    session_cookie = _login_ui(test_client, "ui-user", "ui-pass")

    response = test_client.get("/ui/export", headers=_auth_headers(session_cookie))
    assert response.status_code == 200
    assert "/export/bundle.json" in response.text
    assert "/export/ip-assets.csv" in response.text
    assert "/export/hosts.csv" in response.text
    assert "/export/vendors.csv" not in response.text
    assert "/export/projects.csv" not in response.text


def test_ui_export_page_has_no_template_deprecation_warning(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "ui-user-no-warning", "ui-pass")
    session_cookie = _login_ui(test_client, "ui-user-no-warning", "ui-pass")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        response = test_client.get("/ui/export", headers=_auth_headers(session_cookie))

    assert response.status_code == 200
    template_warnings = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and "TemplateResponse" in str(w.message)
    ]
    assert template_warnings == []


def test_hosts_csv_export_includes_project_and_os_bmc_pair_fields(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "host-export-user", "export-pass")
    _seed_host_export_pair_data(db_path)
    session_cookie = _login_ui(test_client, "host-export-user", "export-pass")

    response = test_client.get(
        "/export/hosts.csv", headers=_auth_headers(session_cookie)
    )
    assert response.status_code == 200

    rows = _parse_csv_rows(response.text)
    assert rows == [
        {
            "name": "node-02",
            "notes": "pair host",
            "vendor_name": "HPE",
            "project_name": "infra",
            "os_ip": "10.10.0.10",
            "bmc_ip": "10.10.0.11",
        }
    ]
