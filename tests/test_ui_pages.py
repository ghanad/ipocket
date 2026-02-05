from __future__ import annotations

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
