from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


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
    assert 'data-testid="stat-active-ips">3<' in response.text
    assert 'data-testid="stat-archived-ips">1<' in response.text
    assert 'data-testid="stat-hosts">1<' in response.text
    assert 'data-testid="stat-vendors">1<' in response.text
    assert 'data-testid="stat-projects">1<' in response.text
    assert 'href="/ui/ip-assets"' in response.text
    assert 'href="/ui/ip-assets?archived-only=true"' in response.text
    assert 'href="/ui/hosts"' in response.text
    assert 'href="/ui/vendors"' in response.text
    assert 'href="/ui/projects"' in response.text
    assert 'class="card-header card-header-padded"' in response.text
    assert "Subnet Utilization" in response.text
    assert "192.168.10.0/24" in response.text
    assert "254</td>" in response.text
    assert 'addresses#used">2</a>' in response.text
    assert 'addresses#free">252</a>' in response.text


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


def test_audit_log_page_lists_ip_entries(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_asset(
            connection, ip_address="10.40.0.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/audit-log")
        assert response.status_code == 200
        assert "10.40.0.10" in response.text
        assert "CREATE" in response.text
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_audit_log_page_lists_import_run_entries(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection,
            username="import-run-view",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        repository.create_audit_log(
            connection,
            user=user,
            action="APPLY",
            target_type="IMPORT_RUN",
            target_id=0,
            target_label="api_import_bundle",
            changes="Import apply source=api_import_bundle; input=bundle.json; create=1; update=0; skip=0; warnings=0; errors=0.",
        )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/audit-log")
        assert response.status_code == 200
        assert "api_import_bundle" in response.text
        assert "APPLY" in response.text
        assert "input=bundle.json" in response.text
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_audit_log_page_pagination(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for i in range(25):
            repository.create_ip_asset(
                connection, ip_address=f"10.45.0.{i}", asset_type=IPAssetType.VM
            )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/audit-log?page=1&per-page=10")
        assert response.status_code == 200
        assert "Showing" in response.text
        assert "Page 1 of" in response.text

        response = client.get("/ui/audit-log?page=2&per-page=10")
        assert response.status_code == 200
        assert "Page 2 of" in response.text

        response = client.get("/ui/audit-log?page=999")
        assert response.status_code == 200
        assert "Page" in response.text
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_row_actions_panel_hidden_style_present() -> None:
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    assert ".row-actions-panel[hidden]" in css
    assert "display: none" in css
