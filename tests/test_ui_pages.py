from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with TestClient(app) as test_client:
        yield test_client
    auth.clear_tokens()


def test_needs_assignment_page_renders(client) -> None:
    response = client.get("/ui/ip-assets/needs-assignment?filter=project")
    assert response.status_code == 200


def test_ip_assets_list_uses_overflow_actions_menu_with_delete_dialog(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(connection, ip_address="10.30.0.10", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert 'data-row-actions' in response.text
    assert 'data-row-actions-toggle' in response.text
    assert 'data-row-actions-panel' in response.text
    assert 'class="row-actions-icon"' in response.text
    assert f'aria-controls="row-actions-{asset.id}"' in response.text
    assert f'data-delete-dialog-id="delete-ip-{asset.id}"' in response.text
    assert f'id="delete-ip-{asset.id}"' in response.text
    assert "Delete IP asset?" in response.text
    assert "Continue to delete" in response.text
    assert "window.addEventListener" in response.text
    assert "positionMenuPanel" in response.text


def test_hosts_list_uses_overflow_actions_menu(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-12", notes="rack-1")
    finally:
        connection.close()

    response = client.get("/ui/hosts")

    assert response.status_code == 200
    assert 'data-row-actions' in response.text
    assert 'data-row-actions-toggle' in response.text
    assert 'data-row-actions-panel' in response.text
    assert 'class="row-actions-icon"' in response.text
    assert f'aria-controls="row-actions-host-{host.id}"' in response.text
    assert f'data-host-edit-toggle="{host.id}"' in response.text
    assert "positionMenuPanel" in response.text


def test_row_actions_panel_hidden_style_present() -> None:
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert ".row-actions-panel[hidden]" in css
    assert "display: none" in css


def test_ui_create_bmc_passes_auto_host_flag_enabled(client, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_ip_asset(connection, **kwargs):
        captured.update(kwargs)
        return IPAsset(
            id=1,
            ip_address=kwargs["ip_address"],
            subnet=kwargs.get("subnet") or "",
            gateway=kwargs.get("gateway") or "",
            asset_type=kwargs["asset_type"],
            project_id=kwargs.get("project_id"),
            host_id=kwargs.get("host_id"),
            notes=kwargs.get("notes"),
            archived=False,
            created_at="",
            updated_at="",
        )

    monkeypatch.delenv("IPOCKET_AUTO_HOST_FOR_BMC", raising=False)
    monkeypatch.setattr("app.routes.ui.repository.create_ip_asset", fake_create_ip_asset)
    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)

    try:
        response = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "192.168.60.10", "type": "BMC"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert captured["asset_type"] == IPAssetType.BMC
    assert captured["auto_host_for_bmc"] is True


def test_ui_create_bmc_passes_auto_host_flag_disabled(client, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_ip_asset(connection, **kwargs):
        captured.update(kwargs)
        return IPAsset(
            id=2,
            ip_address=kwargs["ip_address"],
            subnet=kwargs.get("subnet") or "",
            gateway=kwargs.get("gateway") or "",
            asset_type=kwargs["asset_type"],
            project_id=kwargs.get("project_id"),
            host_id=kwargs.get("host_id"),
            notes=kwargs.get("notes"),
            archived=False,
            created_at="",
            updated_at="",
        )

    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "off")
    monkeypatch.setattr("app.routes.ui.repository.create_ip_asset", fake_create_ip_asset)
    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)

    try:
        response = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "192.168.60.11", "type": "BMC"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert captured["asset_type"] == IPAssetType.BMC
    assert captured["auto_host_for_bmc"] is False



def test_ui_edit_host_updates_name_vendor_and_notes(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        vendor_old = repository.create_vendor(connection, "Dell")
        vendor_new = repository.create_vendor(connection, "HP")
        host = repository.create_host(connection, name="node-01", notes="old", vendor=vendor_old.name)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={"name": "node-01-renamed", "notes": "updated notes", "vendor_id": str(vendor_new.id)},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        updated_host = repository.get_host_by_id(connection, host.id)
    finally:
        connection.close()

    assert updated_host is not None
    assert updated_host.name == "node-01-renamed"
    assert updated_host.notes == "updated notes"
    assert updated_host.vendor == "HP"


def test_ui_edit_host_requires_name(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-02", notes="note")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={"name": "", "notes": "updated"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Host name is required." in response.text


def test_ui_delete_ip_asset_requires_confirmation_text(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(connection, ip_address="10.20.0.10", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        form_response = client.get(f"/ui/ip-assets/{asset.id}/delete")
        response = client.post(
            f"/ui/ip-assets/{asset.id}/delete",
            data={"confirm_ip": "wrong-value"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert form_response.status_code == 200
    assert response.status_code == 400
    assert "برای حذف کامل" in response.text


def test_ui_delete_ip_asset_with_confirmation_text(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(connection, ip_address="10.20.0.11", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/ip-assets/{asset.id}/delete",
            data={"confirm_ip": "10.20.0.11"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        deleted = repository.get_ip_asset_by_ip(connection, "10.20.0.11")
    finally:
        connection.close()

    assert deleted is None


def test_ui_delete_host_requires_confirmation_text(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-delete-01", notes="temp")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        form_response = client.get(f"/ui/hosts/{host.id}/delete")
        response = client.post(
            f"/ui/hosts/{host.id}/delete",
            data={"confirm_name": "wrong-name"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert form_response.status_code == 200
    assert response.status_code == 400
    assert "برای حذف کامل" in response.text


def test_ui_delete_host_with_confirmation_text(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-delete-02", notes="temp")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/delete",
            data={"confirm_name": "node-delete-02"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        deleted = repository.get_host_by_id(connection, host.id)
    finally:
        connection.close()

    assert deleted is None


def test_ui_delete_host_rejects_when_linked_ips_exist(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-delete-03", notes="temp")
        repository.create_ip_asset(connection, ip_address="10.20.0.31", asset_type=IPAssetType.OS, host_id=host.id)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/delete",
            data={"confirm_name": "node-delete-03"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 409
    assert "قابل حذف نیست" in response.text
