from __future__ import annotations

import json

import pytest

from app import repository
from app.models import UserRole
from app.routes.ui import data_ops as data_ops_routes


def _ui_login(client, username: str, password: str) -> None:
    response = client.post(
        "/ui/login",
        data={"username": username, "password": password, "return_to": "/ui/import"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _bundle() -> bytes:
    return json.dumps(
        {
            "app": "ipocket",
            "schema_version": "1",
            "exported_at": "2026-07-17T00:00:00+00:00",
            "data": {
                "vendors": [],
                "projects": [],
                "hosts": [],
                "ip_assets": [
                    {
                        "ip_address": "10.42.0.10",
                        "type": "VM",
                        "project_name": None,
                        "host_name": None,
                        "notes": "react import",
                        "archived": False,
                    }
                ],
            },
        }
    ).encode()


def test_data_ops_react_shell_and_config_expose_viewer_policy(
    client, _create_user
) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    _ui_login(client, "viewer", "viewer-pass")

    page = client.get("/ui/import?tab=export")
    assert page.status_code == 200
    assert 'id="data-ops-root"' in page.text
    assert 'data-endpoint="/api/ui/data-ops"' in page.text
    assert 'data-initial-tab="export"' in page.text
    assert "/static/react/data-ops/data-ops.js" in page.text

    response = client.get("/api/ui/data-ops")
    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"] == {"can_apply": False}
    assert payload["upload"]["max_bytes"] > 0
    assert payload["samples"]["hosts"] == "/static/samples/hosts.csv"
    assert payload["imports"] == {
        "bundle": "/api/ui/import/bundle",
        "csv": "/api/ui/import/csv",
        "nmap": "/api/ui/import/nmap",
    }
    assert set(payload["exports"].values()) == {
        "/export/bundle.json",
        "/export/bundle.zip",
        "/export/ip-assets.csv",
        "/export/ip-assets.json",
        "/export/hosts.csv",
        "/export/hosts.json",
        "/export/vendors.csv",
        "/export/vendors.json",
        "/export/projects.csv",
        "/export/projects.json",
    }


@pytest.mark.parametrize(
    ("method", "url", "files"),
    [
        ("get", "/api/ui/data-ops", None),
        (
            "post",
            "/api/ui/import/bundle?dry_run=1",
            {"file": ("bundle.json", b"{}", "application/json")},
        ),
        (
            "post",
            "/api/ui/import/csv?dry_run=1",
            {"hosts": ("hosts.csv", b"name\nnode", "text/csv")},
        ),
        (
            "post",
            "/api/ui/import/nmap?dry_run=1",
            {"file": ("scan.xml", b"<nmaprun/>", "application/xml")},
        ),
    ],
)
def test_data_ops_react_apis_require_authentication(
    client, method: str, url: str, files
) -> None:
    response = client.request(method, url, files=files, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/login?return_to=")


def test_data_ops_viewer_can_dry_run_all_imports_but_cannot_apply(
    client, _create_user
) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    _ui_login(client, "viewer", "viewer-pass")

    bundle = client.post(
        "/api/ui/import/bundle?dry_run=1",
        files={"file": ("bundle.json", _bundle(), "application/json")},
    )
    assert bundle.status_code == 200
    assert bundle.json()["summary"]["ip_assets"]["would_create"] == 1

    csv = client.post(
        "/api/ui/import/csv?dry_run=1",
        files={
            "ip_assets": (
                "ip-assets.csv",
                (
                    "ip_address,type,project_name,host_name,notes,archived\n"
                    "10.42.0.11,VM,,,csv dry run,false\n"
                ),
                "text/csv",
            )
        },
    )
    assert csv.status_code == 200
    assert csv.json()["summary"]["ip_assets"]["would_create"] == 1

    nmap = client.post(
        "/api/ui/import/nmap?dry_run=1",
        files={
            "file": (
                "scan.xml",
                '<nmaprun><host><status state="up"/><address addr="10.42.0.12" addrtype="ipv4"/></host></nmaprun>',
                "application/xml",
            )
        },
    )
    assert nmap.status_code == 200
    assert nmap.json()["discovered_up_hosts"] == 1

    apply_requests = [
        (
            "/api/ui/import/bundle?dry_run=0",
            {"file": ("bundle.json", _bundle(), "application/json")},
        ),
        (
            "/api/ui/import/csv?dry_run=0",
            {"hosts": ("hosts.csv", b"name\nnode", "text/csv")},
        ),
        (
            "/api/ui/import/nmap?dry_run=0",
            {"file": ("scan.xml", b"<nmaprun/>", "application/xml")},
        ),
    ]
    for url, files in apply_requests:
        assert client.post(url, files=files).status_code == 403


def test_data_ops_editor_can_apply_and_legacy_routes_remain_available(
    client, _create_user, _setup_connection
) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    _ui_login(client, "editor", "editor-pass")

    assert client.get("/api/ui/data-ops").json()["policy"] == {"can_apply": True}
    response = client.post(
        "/api/ui/import/bundle?dry_run=0",
        files={"file": ("bundle.json", _bundle(), "application/json")},
    )
    assert response.status_code == 200

    csv = client.post(
        "/api/ui/import/csv?dry_run=0",
        files={
            "ip_assets": (
                "ip-assets.csv",
                (
                    "ip_address,type,project_name,host_name,notes,archived\n"
                    "10.42.0.11,VM,,,csv apply,false\n"
                ),
                "text/csv",
            )
        },
    )
    assert csv.status_code == 200
    nmap = client.post(
        "/api/ui/import/nmap?dry_run=0",
        files={
            "file": (
                "scan.xml",
                '<nmaprun><host><status state="up"/><address addr="10.42.0.12" addrtype="ipv4"/></host></nmaprun>',
                "application/xml",
            )
        },
    )
    assert nmap.status_code == 200

    connection = _setup_connection()
    try:
        assert repository.get_ip_asset_by_ip(connection, "10.42.0.10") is not None
        assert repository.get_ip_asset_by_ip(connection, "10.42.0.11") is not None
        assert repository.get_ip_asset_by_ip(connection, "10.42.0.12") is not None
    finally:
        connection.close()

    legacy_html = client.post(
        "/ui/import/bundle",
        data={"mode": "dry-run"},
        files={"bundle_file": ("bundle.json", _bundle(), "application/json")},
    )
    assert legacy_html.status_code == 200
    assert client.get("/ui/import").status_code == 200
    assert client.get("/ui/export").status_code == 200
    assert client.get("/export/bundle.json").status_code == 200


def test_data_ops_import_api_validates_missing_and_empty_files(
    client, _create_user
) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    _ui_login(client, "viewer", "viewer-pass")

    assert client.post("/api/ui/import/csv?dry_run=1").status_code == 400
    empty = client.post(
        "/api/ui/import/bundle?dry_run=1",
        files={"file": ("bundle.json", b"", "application/json")},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"] == "bundle.json file is empty."
    empty_nmap = client.post(
        "/api/ui/import/nmap?dry_run=1",
        files={"file": ("scan.xml", b"", "application/xml")},
    )
    assert empty_nmap.status_code == 400
    assert empty_nmap.json()["detail"] == "Nmap XML file is empty."


@pytest.mark.parametrize(
    ("url", "files"),
    [
        (
            "/api/ui/import/bundle?dry_run=1",
            {"file": ("bundle.json", b"01234567890", "application/json")},
        ),
        (
            "/api/ui/import/csv?dry_run=1",
            {"hosts": ("hosts.csv", b"01234567890", "text/csv")},
        ),
        (
            "/api/ui/import/nmap?dry_run=1",
            {"file": ("scan.xml", b"01234567890", "application/xml")},
        ),
    ],
)
def test_data_ops_react_import_apis_reject_oversized_uploads(
    client, _create_user, monkeypatch, url: str, files
) -> None:
    monkeypatch.setattr(data_ops_routes, "IMPORT_UPLOAD_MAX_BYTES", 10)
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    _ui_login(client, "viewer", "viewer-pass")

    response = client.post(url, files=files)
    assert response.status_code == 413
    assert response.json()["detail"] == "Uploaded file exceeds maximum size of 10 bytes."
