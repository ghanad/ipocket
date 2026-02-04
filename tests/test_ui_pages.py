from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from http.cookies import SimpleCookie

from app import auth, db, repository
from app.main import SESSION_COOKIE, app
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


def _ui_login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/ui/login",
        data={"username": username, "password": password},
        allow_redirects=False,
    )
    assert response.status_code == 303
    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    if SESSION_COOKIE in cookie:
        cookie_value = cookie[SESSION_COOKIE].value
        client.headers.update(
            {"Cookie": f"{SESSION_COOKIE}={cookie_value}"}
        )


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
    _ui_login(test_client, "viewer", "viewer-pass")

    response = test_client.post(
        "/ui/ip-assets/new",
        data={
            "ip_address": "10.0.2.20",
            "subnet": "10.0.2.0/24",
            "gateway": "10.0.2.1",
            "type": IPAssetType.VM.value,
        },
        allow_redirects=False,
    )

    assert response.status_code == 403


def test_ui_new_route_redirects_when_unauthenticated(client) -> None:
    test_client, _db_path = client
    response = test_client.get("/ui/ip-assets/new", allow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/login"


def test_needs_assignment_filters(client) -> None:
    test_client, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        owner = repository.create_owner(connection, name="NetOps")
        repository.create_ip_asset(
            connection,
            ip_address="10.0.3.10",
            subnet="10.0.3.0/24",
            gateway="10.0.3.1",
            asset_type=IPAssetType.VM,
            owner_id=owner.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.3.11",
            subnet="10.0.3.0/24",
            gateway="10.0.3.1",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.3.12",
            subnet="10.0.3.0/24",
            gateway="10.0.3.1",
            asset_type=IPAssetType.VIP,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.3.13",
            subnet="10.0.3.0/24",
            gateway="10.0.3.1",
            asset_type=IPAssetType.VIP,
            project_id=project.id,
            owner_id=owner.id,
        )
    finally:
        connection.close()

    owner_filter = test_client.get(
        "/ui/ip-assets/needs-assignment?filter=owner"
    )
    assert owner_filter.status_code == 200
    assert "10.0.3.11" in owner_filter.text
    assert "10.0.3.12" in owner_filter.text
    assert "10.0.3.10" not in owner_filter.text
    assert "10.0.3.13" not in owner_filter.text

    project_filter = test_client.get(
        "/ui/ip-assets/needs-assignment?filter=project"
    )
    assert project_filter.status_code == 200
    assert "10.0.3.10" in project_filter.text
    assert "10.0.3.12" in project_filter.text
    assert "10.0.3.11" not in project_filter.text
    assert "10.0.3.13" not in project_filter.text

    both_filter = test_client.get(
        "/ui/ip-assets/needs-assignment?filter=both"
    )
    assert both_filter.status_code == 200
    assert "10.0.3.12" in both_filter.text
    assert "10.0.3.10" not in both_filter.text
    assert "10.0.3.11" not in both_filter.text
    assert "10.0.3.13" not in both_filter.text


def test_needs_assignment_assigns_owner_project(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    _ui_login(test_client, "editor", "editor-pass")

    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        owner = repository.create_owner(connection, name="NetOps")
        repository.create_ip_asset(
            connection,
            ip_address="10.0.4.10",
            subnet="10.0.4.0/24",
            gateway="10.0.4.1",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    response = test_client.post(
        "/ui/ip-assets/needs-assignment/assign?filter=both",
        data={
            "ip_address": "10.0.4.10",
            "project_id": str(project.id),
            "owner_id": str(owner.id),
        },
        allow_redirects=False,
    )
    assert response.status_code == 303

    detail_response = test_client.get("/ip-assets/10.0.4.10")
    assert detail_response.status_code == 200
    assert detail_response.json()["project_id"] == project.id
    assert detail_response.json()["owner_id"] == owner.id


def test_needs_assignment_rejects_viewer(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    _ui_login(test_client, "viewer", "viewer-pass")

    response = test_client.post(
        "/ui/ip-assets/needs-assignment/assign?filter=owner",
        data={
            "ip_address": "10.0.5.10",
            "project_id": "",
            "owner_id": "",
        },
        allow_redirects=False,
    )
    assert response.status_code == 403


def test_editor_can_create_ip_via_ui(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    _ui_login(test_client, "editor", "editor-pass")

    form_response = test_client.get("/ui/ip-assets/new")
    assert form_response.status_code == 200

    submit_response = test_client.post(
        "/ui/ip-assets/new",
        data={
            "ip_address": "10.0.8.10",
            "subnet": "10.0.8.0/24",
            "gateway": "10.0.8.1",
            "type": IPAssetType.VM.value,
        },
        allow_redirects=False,
    )
    assert submit_response.status_code == 303
    assert submit_response.headers["location"].startswith("/ui/ip-assets/")

    list_response = test_client.get("/ui/ip-assets")
    assert list_response.status_code == 200
    assert "10.0.8.10" in list_response.text


def test_ui_includes_pico_css(client) -> None:
    test_client, _db_path = client
    response = test_client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert "pico.min.css" in response.text
