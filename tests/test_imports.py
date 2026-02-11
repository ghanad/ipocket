from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from app import auth, db, exports, repository
from app.imports import BundleImporter, run_import
from app.main import app
from app.models import IPAssetType, UserRole


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with FastAPITestClient(app) as test_client:
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


def _login(client: FastAPITestClient, username: str, password: str) -> str:
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bundle_payload() -> dict:
    return {
        "app": "ipocket",
        "schema_version": "1",
        "exported_at": "2024-01-01T12:00:00+00:00",
        "data": {
            "vendors": [{"name": "HPE"}],
            "projects": [{"name": "Core", "description": "Core project", "color": "#1d4ed8"}],
            "hosts": [{"name": "node-01", "notes": "primary", "vendor_name": "HPE"}],
            "ip_assets": [
                {
                    "ip_address": "10.0.0.10",
                    "type": "VM",
                    "project_name": "Core",
                    "host_name": "node-01",
                    "notes": "prod",
                    "archived": False,
                }
            ],
        },
    }


def test_bundle_json_dry_run_does_not_write(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    token = _login(test_client, "viewer", "viewer-pass")

    payload = json.dumps(_bundle_payload()).encode("utf-8")
    response = test_client.post(
        "/import/bundle?dry_run=1",
        headers=_auth_headers(token),
        files={"file": ("bundle.json", payload, "application/json")},
    )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total"]["would_create"] == 4

    connection = db.connect(str(db_path))
    try:
        assert list(repository.list_vendors(connection)) == []
        assert list(repository.list_projects(connection)) == []
        assert list(repository.list_hosts(connection)) == []
        assert list(repository.list_active_ip_assets(connection)) == []
    finally:
        connection.close()


def test_bundle_json_apply_creates_and_updates(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)
    token = _login(test_client, "editor", "editor-pass")

    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        repository.create_project(connection, name="Core", description="Old", color="#94a3b8")
    finally:
        connection.close()

    payload = json.dumps(_bundle_payload()).encode("utf-8")
    response = test_client.post(
        "/import/bundle",
        headers=_auth_headers(token),
        files={"file": ("bundle.json", payload, "application/json")},
    )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["projects"]["would_update"] == 1

    connection = db.connect(str(db_path))
    try:
        project = repository.list_projects(connection)[0]
        assert project.description == "Core project"
        vendor = repository.get_vendor_by_name(connection, "HPE")
        assert vendor is not None
        host = repository.get_host_by_name(connection, "node-01")
        assert host is not None
        asset = repository.get_ip_asset_by_ip(connection, "10.0.0.10")
        assert asset is not None
        assert asset.asset_type == IPAssetType.VM
        assert asset.project_id == project.id
        assert asset.host_id == host.id
    finally:
        connection.close()


def test_csv_dry_run_and_apply(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)

    hosts_csv = "name,notes,vendor_name\nnode-02,worker,Dell\n"
    ip_assets_csv = "ip_address,type,project_name,host_name,notes,archived\n10.0.0.20,OS,Core,node-02,os,false\n"

    viewer_token = _login(test_client, "viewer", "viewer-pass")
    dry_run_response = test_client.post(
        "/import/csv?dry_run=1",
        headers=_auth_headers(viewer_token),
        files={
            "hosts": ("hosts.csv", hosts_csv, "text/csv"),
            "ip_assets": ("ip-assets.csv", ip_assets_csv, "text/csv"),
        },
    )
    assert dry_run_response.status_code == 200
    assert dry_run_response.json()["summary"]["ip_assets"]["would_create"] == 1

    connection = db.connect(str(db_path))
    try:
        assert list(repository.list_hosts(connection)) == []
    finally:
        connection.close()

    editor_token = _login(test_client, "editor", "editor-pass")
    apply_response = test_client.post(
        "/import/csv",
        headers=_auth_headers(editor_token),
        files={
            "hosts": ("hosts.csv", hosts_csv, "text/csv"),
            "ip_assets": ("ip-assets.csv", ip_assets_csv, "text/csv"),
        },
    )
    assert apply_response.status_code == 200

    connection = db.connect(str(db_path))
    try:
        assert repository.get_host_by_name(connection, "node-02") is not None
        assert repository.get_vendor_by_name(connection, "Dell") is not None
        projects = list(repository.list_projects(connection))
        assert any(project.name == "Core" for project in projects)
        asset = repository.get_ip_asset_by_ip(connection, "10.0.0.20")
        assert asset is not None
        assert asset.asset_type == IPAssetType.OS
    finally:
        connection.close()


def test_csv_dry_run_single_file_imports(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)

    viewer_token = _login(test_client, "viewer", "viewer-pass")

    hosts_csv = "name,notes,vendor_name\nnode-03,edge,Cisco\n"
    hosts_only_response = test_client.post(
        "/import/csv?dry_run=1",
        headers=_auth_headers(viewer_token),
        files={"hosts": ("hosts.csv", hosts_csv, "text/csv")},
    )
    assert hosts_only_response.status_code == 200
    hosts_summary = hosts_only_response.json()["summary"]
    assert hosts_summary["hosts"]["would_create"] == 1
    assert hosts_summary["vendors"]["would_create"] == 1
    assert hosts_summary["ip_assets"]["would_create"] == 0

    ip_assets_csv = "ip_address,type,project_name,host_name,notes,archived\n10.0.0.30,VM,Solo,,edge,false\n"
    ip_assets_only_response = test_client.post(
        "/import/csv?dry_run=1",
        headers=_auth_headers(viewer_token),
        files={"ip_assets": ("ip-assets.csv", ip_assets_csv, "text/csv")},
    )
    assert ip_assets_only_response.status_code == 200
    assets_summary = ip_assets_only_response.json()["summary"]
    assert assets_summary["projects"]["would_create"] == 1
    assert assets_summary["ip_assets"]["would_create"] == 1
    assert assets_summary["hosts"]["would_create"] == 0


def test_csv_import_hosts_with_os_bmc_ips(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    _create_user(db_path, "editor", "editor-pass", UserRole.EDITOR)

    hosts_csv = (
        "name,notes,vendor_name,project_name,os_ip,bmc_ip\n"
        "node-10,edge,Dell,Core,10.0.0.50,10.0.0.51\n"
    )

    viewer_token = _login(test_client, "viewer", "viewer-pass")
    dry_run_response = test_client.post(
        "/import/csv?dry_run=1",
        headers=_auth_headers(viewer_token),
        files={"hosts": ("hosts.csv", hosts_csv, "text/csv")},
    )
    assert dry_run_response.status_code == 200
    summary = dry_run_response.json()["summary"]
    assert summary["hosts"]["would_create"] == 1
    assert summary["vendors"]["would_create"] == 1
    assert summary["ip_assets"]["would_create"] == 2

    editor_token = _login(test_client, "editor", "editor-pass")
    apply_response = test_client.post(
        "/import/csv",
        headers=_auth_headers(editor_token),
        files={"hosts": ("hosts.csv", hosts_csv, "text/csv")},
    )
    assert apply_response.status_code == 200

    connection = db.connect(str(db_path))
    try:
        host = repository.get_host_by_name(connection, "node-10")
        assert host is not None
        os_asset = repository.get_ip_asset_by_ip(connection, "10.0.0.50")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.0.0.51")
        assert os_asset is not None
        assert bmc_asset is not None
        assert os_asset.asset_type == IPAssetType.OS
        assert bmc_asset.asset_type == IPAssetType.BMC
        assert os_asset.project_id is not None
        assert bmc_asset.project_id is not None
        assert os_asset.project_id == bmc_asset.project_id
        assert os_asset.host_id == host.id
        assert bmc_asset.host_id == host.id
    finally:
        connection.close()


def test_csv_ignores_empty_optional_file(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)

    viewer_token = _login(test_client, "viewer", "viewer-pass")
    ip_assets_csv = "ip_address,type,project_name,host_name,notes,archived\n10.0.0.40,VM,Solo,,edge,false\n"
    response = test_client.post(
        "/import/csv?dry_run=1",
        headers=_auth_headers(viewer_token),
        files={
            "hosts": ("hosts.csv", "", "text/csv"),
            "ip_assets": ("ip-assets.csv", ip_assets_csv, "text/csv"),
        },
    )
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["ip_assets"]["would_create"] == 1
    assert summary["hosts"]["would_create"] == 0


def test_validation_errors(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    token = _login(test_client, "viewer", "viewer-pass")

    payload = {
        "app": "ipocket",
        "schema_version": "1",
        "exported_at": "2024-01-01T12:00:00+00:00",
        "data": {
            "vendors": [{"name": ""}],
            "projects": [{"name": "", "color": "not-a-color"}],
            "hosts": [{"name": "", "vendor_name": "Missing"}],
            "ip_assets": [
                {"ip_address": "999.0.0.1", "type": "BAD"},
            ],
        },
    }

    response = test_client.post(
        "/import/bundle?dry_run=1",
        headers=_auth_headers(token),
        files={"file": ("bundle.json", json.dumps(payload), "application/json")},
    )
    assert response.status_code == 200
    errors = response.json()["errors"]
    messages = {error["message"] for error in errors}
    assert "Vendor name is required." in messages
    assert "Project name is required." in messages
    assert "Color must be a hex value like #1a2b3c." in messages
    assert "Host name is required." in messages
    assert "Vendor does not exist." in messages
    assert "Invalid IP address." in messages
    assert "Invalid asset type. Use OS, BMC, VM, VIP, OTHER." in messages


def test_viewer_cannot_apply_import(client) -> None:
    test_client, db_path = client
    _create_user(db_path, "viewer", "viewer-pass", UserRole.VIEWER)
    token = _login(test_client, "viewer", "viewer-pass")

    response = test_client.post(
        "/import/bundle",
        headers=_auth_headers(token),
        files={"file": ("bundle.json", json.dumps(_bundle_payload()), "application/json")},
    )
    assert response.status_code == 403


def test_round_trip_bundle_import(tmp_path) -> None:
    source_connection = db.connect(str(tmp_path / "source.db"))
    try:
        db.init_db(source_connection)
        vendor = repository.create_vendor(source_connection, "HPE")
        project = repository.create_project(source_connection, "Core", "Core project", "#1d4ed8")
        host = repository.create_host(source_connection, "node-03", "notes", vendor.name)
        asset = repository.create_ip_asset(
            source_connection,
            ip_address="10.0.0.30",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
            notes="primary",
            tags=["prod", "edge"],
        )
        bundle = exports.export_bundle(source_connection)
    finally:
        source_connection.close()

    target_connection = db.connect(str(tmp_path / "target.db"))
    try:
        db.init_db(target_connection)
        result = run_import(
            target_connection,
            BundleImporter(),
            {"bundle": json.dumps(bundle).encode("utf-8")},
            dry_run=False,
        )
        assert result.errors == []
        assert len(repository.list_projects(target_connection)) == 1
        assert len(repository.list_hosts(target_connection)) == 1
        assert len(repository.list_vendors(target_connection)) == 1
        imported = repository.get_ip_asset_by_ip(target_connection, "10.0.0.30")
        assert imported is not None
        tag_map = repository.list_tags_for_ip_assets(target_connection, [imported.id])
        assert tag_map[imported.id] == ["edge", "prod"]
    finally:
        target_connection.close()
