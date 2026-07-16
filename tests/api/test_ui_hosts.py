from __future__ import annotations

import os

import pytest

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes.ui.hosts.common import require_ui_host_writer
from app.routes.ui.utils import get_current_ui_user


def _user(role: UserRole) -> User:
    return User(1, role.value.lower(), "x", role, True)


@pytest.fixture
def editor_override():
    app.dependency_overrides[get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    app.dependency_overrides[require_ui_host_writer] = lambda: _user(
        UserRole.EDITOR
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_ui_user, None)
        app.dependency_overrides.pop(require_ui_host_writer, None)


def test_ui_hosts_api_lists_filters_links_tags_and_pagination(
    client, editor_override
) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        project = repository.create_project(
            connection, name="Core", color="#2563eb"
        )
        vendor = repository.create_vendor(connection, name="Dell")
        repository.create_tag(connection, name="prod", color="#22c55e")
        host = repository.create_host(connection, name="edge-01", vendor=vendor.name)
        os_asset = repository.create_ip_asset(
            connection,
            ip_address="10.40.0.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
            tags=["prod"],
        )
        repository.create_host(connection, name="free-01")
    finally:
        connection.close()

    response = client.get(
        "/api/ui/hosts",
        params={"project_id": project.id, "status": "linked", "tag": "prod"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_edit"] is True
    assert payload["pagination"]["total"] == 1
    assert payload["hosts"][0]["id"] == host.id
    assert payload["hosts"][0]["project_id"] == project.id
    assert payload["hosts"][0]["os_ip_links"] == [
        {"id": os_asset.id, "ip_address": "10.40.0.10"}
    ]
    assert payload["hosts"][0]["ip_tags"] == [
        {"name": "prod", "color": "#22c55e"}
    ]
    assert payload["filters"]["projects"][0]["name"] == "Core"
    assert payload["filters"]["vendors"][0]["name"] == "Dell"


def test_ui_hosts_api_filters_search_assignment_vendor_and_free(
    client, editor_override
) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        vendor = repository.create_vendor(connection, name="Cisco")
        linked = repository.create_host(
            connection, name="linked-node", vendor=vendor.name
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.50.0.10",
            asset_type=IPAssetType.BMC,
            host_id=linked.id,
        )
        repository.create_host(connection, name="free-node", vendor=vendor.name)
    finally:
        connection.close()

    free = client.get(
        "/api/ui/hosts",
        params={"q": "free", "vendor_id": vendor.id, "status": "free"},
    )
    unassigned = client.get(
        "/api/ui/hosts", params={"unassigned-only": "true"}
    )

    assert [item["name"] for item in free.json()["hosts"]] == ["free-node"]
    assert {item["name"] for item in unassigned.json()["hosts"]} == {
        "free-node",
        "linked-node",
    }


def test_ui_hosts_api_create_update_delete_unlinks_ips(
    client, editor_override
) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        project = repository.create_project(connection, name="Platform")
        vendor = repository.create_vendor(connection, name="Dell")
    finally:
        connection.close()

    created = client.post(
        "/api/ui/hosts",
        json={
            "name": "node-01",
            "vendor_id": vendor.id,
            "project_id": project.id,
            "os_ips": ["10.60.0.10"],
            "bmc_ips": ["10.60.0.11"],
            "notes": "rack-a",
        },
    )
    assert created.status_code == 201
    host_id = created.json()["id"]

    updated = client.patch(
        f"/api/ui/hosts/{host_id}",
        json={
            "name": "node-01-renamed",
            "vendor_id": None,
            "project_id": None,
            "os_ips": ["10.60.0.10"],
            "bmc_ips": [],
            "notes": "",
        },
    )
    assert updated.status_code == 200

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        host = repository.get_host_by_id(connection, host_id)
        os_asset = repository.get_ip_asset_by_ip(connection, "10.60.0.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.60.0.11")
        assert host and host.vendor is None and host.notes is None
        assert os_asset and os_asset.host_id == host_id and os_asset.project_id is None
        assert bmc_asset and bmc_asset.host_id is None
    finally:
        connection.close()

    wrong = client.request(
        "DELETE",
        f"/api/ui/hosts/{host_id}",
        json={"confirm_name": "wrong"},
    )
    assert wrong.status_code == 400
    deleted = client.request(
        "DELETE",
        f"/api/ui/hosts/{host_id}",
        json={"confirm_name": "node-01-renamed"},
    )
    assert deleted.status_code == 204

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        assert repository.get_host_by_id(connection, host_id) is None
        assert repository.get_ip_asset_by_ip(connection, "10.60.0.10").host_id is None
    finally:
        connection.close()


def test_ui_hosts_api_update_can_preserve_multiple_projects(
    client, editor_override
) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        first = repository.create_project(connection, name="First")
        second = repository.create_project(connection, name="Second")
        host = repository.create_host(connection, name="mixed-project-host")
        repository.create_ip_asset(
            connection,
            ip_address="10.61.0.10",
            asset_type=IPAssetType.OS,
            project_id=first.id,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.61.0.11",
            asset_type=IPAssetType.BMC,
            project_id=second.id,
            host_id=host.id,
        )
    finally:
        connection.close()

    response = client.patch(
        f"/api/ui/hosts/{host.id}",
        json={
            "name": "mixed-project-host-renamed",
            "os_ips": ["10.61.0.10"],
            "bmc_ips": ["10.61.0.11"],
        },
    )
    assert response.status_code == 200

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        assert repository.get_ip_asset_by_ip(
            connection, "10.61.0.10"
        ).project_id == first.id
        assert repository.get_ip_asset_by_ip(
            connection, "10.61.0.11"
        ).project_id == second.id
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"name": " "}, "Host name is required."),
        ({"name": "node", "vendor_id": 999}, "Selected vendor does not exist."),
        ({"name": "node", "project_id": 999}, "Selected project does not exist."),
        ({"name": "node", "os_ips": ["bad-ip"]}, "Invalid IP address"),
    ],
)
def test_ui_hosts_api_validation(client, editor_override, payload, message) -> None:
    response = client.post("/api/ui/hosts", json=payload)
    assert response.status_code == 422
    assert message in response.text


def test_ui_hosts_api_authentication_and_roles(client, _create_user) -> None:
    unauthenticated = client.get("/api/ui/hosts", follow_redirects=False)
    assert unauthenticated.status_code == 303
    assert "/ui/login?return_to=/api/ui/hosts" in unauthenticated.headers["location"]

    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    login = client.post(
        "/ui/login",
        data={"username": "viewer", "password": "viewer-pass"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert client.get("/api/ui/hosts").json()["can_edit"] is False
    assert client.post("/api/ui/hosts", json={"name": "denied"}).status_code == 403


@pytest.mark.parametrize("role", [UserRole.EDITOR, UserRole.SUPERUSER])
def test_ui_hosts_api_allows_editor_and_superuser_writes(
    client, _create_user, role
) -> None:
    username = role.value.lower()
    _create_user(username, "pass", role)
    client.post(
        "/ui/login",
        data={"username": username, "password": "pass"},
        follow_redirects=False,
    )
    response = client.post("/api/ui/hosts", json={"name": f"{username}-host"})
    assert response.status_code == 201


def test_hosts_page_uses_react_mount_and_keeps_detail_route(
    client, editor_override
) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        host = repository.create_host(connection, name="detail-host")
    finally:
        connection.close()

    page = client.get("/ui/hosts", params={"status": "free"})
    detail = client.get(f"/ui/hosts/{host.id}")

    assert page.status_code == 200
    assert 'id="hosts-root"' in page.text
    assert 'data-initial-query="status=free"' in page.text
    assert "/static/react/hosts/hosts.js" in page.text
    assert detail.status_code == 200
    assert "detail-host" in detail.text
