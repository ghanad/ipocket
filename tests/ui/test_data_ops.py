from __future__ import annotations

import io
import zipfile

from app import repository
from app.imports.models import (
    ImportApplyResult,
    ImportEntitySummary,
    ImportIssue,
    ImportSummary,
)
from app.imports.nmap import NmapImportAsset, NmapImportResult
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from app.routes.ui import data_ops as data_ops_routes


def _user(role: UserRole) -> User:
    return User(1, role.value.lower(), "x", role, True)


def _summary() -> ImportSummary:
    return ImportSummary(
        vendors=ImportEntitySummary(would_create=1, would_update=0, would_skip=0),
        projects=ImportEntitySummary(would_create=0, would_update=1, would_skip=0),
        hosts=ImportEntitySummary(would_create=0, would_update=0, would_skip=1),
        ip_assets=ImportEntitySummary(would_create=1, would_update=1, would_skip=1),
    )


def test_nmap_import_validation_and_apply_branches(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    try:
        missing_file = client.post("/ui/import/nmap", data={"mode": "dry-run"})
        empty_file = client.post(
            "/ui/import/nmap",
            data={"mode": "dry-run"},
            files={"nmap_file": ("scan.xml", b"", "text/xml")},
        )

        monkeypatch.setattr(
            data_ops_routes,
            "import_nmap_xml",
            lambda *_args, **_kwargs: NmapImportResult(
                discovered_up_hosts=2,
                new_ips_created=1,
                existing_ips_seen=1,
                errors=["invalid host"],
                new_assets=[NmapImportAsset(id=99, ip_address="10.0.0.99")],
            ),
        )
        apply_with_errors = client.post(
            "/ui/import/nmap",
            data={"mode": "apply"},
            files={"nmap_file": ("scan.xml", b"<nmaprun />", "text/xml")},
        )

        monkeypatch.setattr(
            data_ops_routes,
            "import_nmap_xml",
            lambda *_args, **_kwargs: NmapImportResult(
                discovered_up_hosts=1,
                new_ips_created=1,
                existing_ips_seen=0,
                errors=[],
                new_assets=[],
            ),
        )
        apply_success = client.post(
            "/ui/import/nmap",
            data={"mode": "apply"},
            files={"nmap_file": ("scan.xml", b"<nmaprun />", "text/xml")},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert missing_file.status_code == 400
    assert "Nmap XML file is required." in missing_file.text
    assert empty_file.status_code == 400
    assert "Nmap XML file is empty." in empty_file.text
    assert apply_with_errors.status_code == 200
    assert "Discovered up hosts: 2" in apply_with_errors.text
    assert "invalid host" in apply_with_errors.text
    assert '/ui/ip-assets/99' in apply_with_errors.text
    assert apply_success.status_code == 200
    assert "Discovered up hosts: 1" in apply_success.text


def test_bundle_import_validation_and_result_payload_rendering(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    try:
        viewer_forbidden = client.post(
            "/ui/import/bundle",
            data={"mode": "apply"},
            files={"bundle_file": ("bundle.json", b"{}", "application/json")},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    try:
        missing_file = client.post("/ui/import/bundle", data={"mode": "dry-run"})

        monkeypatch.setattr(
            data_ops_routes,
            "run_import",
            lambda *_args, **_kwargs: ImportApplyResult(
                summary=_summary(),
                errors=[ImportIssue(location="bundle.projects[0]", message="bad row")],
                warnings=[ImportIssue(location="bundle.hosts[0]", message="warn")],
            ),
        )
        rendered = client.post(
            "/ui/import/bundle",
            data={"mode": "apply"},
            files={"bundle_file": ("bundle.json", b"{}", "application/json")},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert viewer_forbidden.status_code == 403
    assert missing_file.status_code == 400
    assert "bundle.json file is required." in missing_file.text
    assert rendered.status_code == 200
    assert "Total: 2 create, 2 update, 2 skip" in rendered.text
    assert "bundle.projects[0]: bad row" in rendered.text
    assert "bundle.hosts[0]: warn" in rendered.text


def test_csv_import_validation_and_result_payload_rendering(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    try:
        viewer_forbidden = client.post(
            "/ui/import/csv",
            data={"mode": "apply"},
            files={"hosts_file": ("hosts.csv", b"name\nnode\n", "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    try:
        missing_both = client.post("/ui/import/csv", data={"mode": "dry-run"})
        empty_both = client.post(
            "/ui/import/csv",
            data={"mode": "dry-run"},
            files={
                "hosts_file": ("hosts.csv", b"", "text/csv"),
                "ip_assets_file": ("ip-assets.csv", b"", "text/csv"),
            },
        )

        monkeypatch.setattr(
            data_ops_routes,
            "run_import",
            lambda *_args, **_kwargs: ImportApplyResult(
                summary=_summary(),
                errors=[ImportIssue(location="csv.ip_assets[0]", message="bad ip")],
                warnings=[],
            ),
        )
        rendered = client.post(
            "/ui/import/csv",
            data={"mode": "apply"},
            files={
                "hosts_file": ("hosts.csv", b"name\nnode\n", "text/csv"),
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert viewer_forbidden.status_code == 403
    assert missing_both.status_code == 400
    assert "Upload at least one CSV file" in missing_both.text
    assert empty_both.status_code == 400
    assert "Upload at least one non-empty CSV file" in empty_both.text
    assert rendered.status_code == 200
    assert "Total: 2 create, 2 update, 2 skip" in rendered.text
    assert "csv.ip_assets[0]: bad ip" in rendered.text


def test_export_bundle_zip_contains_expected_files(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        vendor = repository.create_vendor(connection, "Dell")
        project = repository.create_project(
            connection, name="core", description="Core", color="#123456"
        )
        host = repository.create_host(connection, "node-01", vendor=vendor.name)
        repository.create_ip_asset(
            connection,
            ip_address="10.1.1.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
            tags=["prod"],
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = client.get("/export/bundle.zip")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response._content))
    assert set(archive.namelist()) == {
        "bundle.json",
        "ip-assets.csv",
        "projects.csv",
        "hosts.csv",
        "vendors.csv",
    }
    assert "10.1.1.10" in archive.read("ip-assets.csv").decode("utf-8")
