from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def _read_application_css() -> str:
    static_css = Path("app/static/css")
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(static_css.glob("*.css"))
    )


def test_needs_assignment_route_removed(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/ip-assets/needs-assignment?filter=project")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_needs_assignment_links_removed_from_ui(client) -> None:
    response = client.get("/ui/ip-assets")
    assert response.status_code == 200
    assert "/ui/ip-assets/needs-assignment" not in response.text


def test_management_page_shows_summary_counts(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Apps")
        vendor = repository.create_vendor(connection, name="Lenovo")
        host = repository.create_host(connection, name="edge-01", vendor=vendor.name)
        repository.create_ip_asset(
            connection,
            ip_address="10.50.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
        )
        archived_asset = repository.create_ip_asset(
            connection, ip_address="10.50.0.11", asset_type=IPAssetType.OS
        )
        repository.archive_ip_asset(connection, archived_asset.ip_address)
        repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
        repository.create_ip_asset(
            connection, ip_address="192.168.10.10", asset_type=IPAssetType.VM
        )
        repository.create_ip_asset(
            connection, ip_address="192.168.10.11", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "Management Overview" in response.text
    assert 'id="management-root"' in response.text
    assert 'class="management-root"' in response.text
    assert 'data-endpoint="/api/management/overview"' in response.text
    assert (
        '<script type="module" src="/static/react/management/management.js"></script>'
        in response.text
    )


def test_management_react_root_preserves_page_section_spacing() -> None:
    css = _read_application_css()

    assert ".management-root {" in css
    assert "flex-direction: column;" in css
    assert "gap: 24px;" in css


def test_flash_messages_render_once(client) -> None:
    payload = [{"type": "success", "message": "Saved successfully."}]
    encoded = ui._encode_flash_payload(payload)
    signed = ui._sign_session_value(encoded)
    response = client.get(
        "/ui/management",
        headers={"Cookie": f"{ui.FLASH_COOKIE}={signed}"},
    )

    assert response.status_code == 200
    assert "Saved successfully." in response.text
    assert "toast-container" in response.text
    assert ui.FLASH_COOKIE in response.headers.get("set-cookie", "")

    followup = client.get("/ui/management")
    assert "Saved successfully." not in followup.text


def test_row_actions_panel_hidden_style_present() -> None:
    css = _read_application_css()
    assert ".row-actions-panel[hidden]" in css
    assert "display: none" in css
