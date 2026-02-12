from __future__ import annotations

from app.connectors.vcenter import VCenterHostRecord, VCenterVmRecord
from app.imports.models import ImportApplyResult, ImportEntitySummary, ImportSummary
from app.main import app
from app.models import User, UserRole
from app.routes import ui
from app.routes.ui import connectors as connectors_routes


def test_connectors_page_renders_sidebar_link_and_tabs(client) -> None:
    response = client.get("/ui/connectors")

    assert response.status_code == 200
    assert 'href="/ui/connectors"' in response.text
    assert "Integrations" in response.text
    assert 'href="/ui/connectors?tab=overview"' in response.text
    assert 'href="/ui/connectors?tab=vcenter"' in response.text
    assert "Available Connectors" in response.text
    assert "vCenter" in response.text


def test_connectors_vcenter_tab_renders_connector_commands(client) -> None:
    response = client.get("/ui/connectors?tab=vcenter")

    assert response.status_code == 200
    assert "Run vCenter Connector" in response.text
    assert 'action="/ui/connectors/vcenter/run"' in response.text
    assert 'name="mode"' in response.text
    assert "Execution log" not in response.text


def test_vcenter_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "apply",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_vcenter_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_vcenter_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "vCenter dry-run completed successfully." in response.text
    assert "toast-success" in response.text


def test_vcenter_connector_ui_runs_dry_run_and_shows_logs(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "fetch_vcenter_inventory",
        lambda **_kwargs: (
            [VCenterHostRecord(name="esxi-01.lab", ip_address="10.20.30.40")],
            [
                VCenterVmRecord(
                    name="app-vm-01",
                    ip_address="10.20.30.50",
                    host_name="esxi-01.lab",
                )
            ],
            ["Skipped VM 'no-ip' because no IPv4 guest IP was found."],
        ),
    )
    monkeypatch.setattr(
        connectors_routes,
        "run_import",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(would_create=1),
                ip_assets=ImportEntitySummary(
                    would_create=2, would_update=0, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 1 hosts and 1 VMs." in response.text
    assert "Import mode: dry-run." in response.text
    assert "Connector warnings: 1" in response.text
    assert "completed with warnings" in response.text
    assert "toast-warning" in response.text


def test_vcenter_connector_ui_validates_required_fields(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            data={"server": "", "username": "", "password": "", "mode": "dry-run"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "vCenter server is required." in response.text
    assert "vCenter username is required." in response.text
    assert "vCenter password is required." in response.text


def test_vcenter_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_vcenter_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.VCenterConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "vCenter connector execution failed." in response.text
    assert "toast-error" in response.text
