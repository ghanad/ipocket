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


def test_management_page_shows_summary_counts(client) -> None:
    import os
    from app import db, repository

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
        repository.create_ip_asset(connection, ip_address="192.168.10.10", asset_type=IPAssetType.VM)
        repository.create_ip_asset(connection, ip_address="192.168.10.11", asset_type=IPAssetType.VM)
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


def test_ranges_page_renders_add_form_and_saved_ranges(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
    finally:
        connection.close()

    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert "Add IP Range" in response.text
    assert "192.168.10.0/24" in response.text
    assert "Saved ranges" in response.text
    assert "data-row-actions" in response.text


def test_range_addresses_page_shows_tags(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(connection, name="Lab Range", cidr="10.40.0.0/24")
        host = repository.create_host(connection, name="lab-01")
        repository.create_tag(connection, name="core", color="#1d4ed8")
        repository.create_ip_asset(
            connection,
            ip_address="10.40.0.10",
            asset_type=IPAssetType.OS,
            tags=["core"],
            host_id=host.id,
            notes="primary",
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.40.0.11",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ranges/{ip_range.id}/addresses")

    assert response.status_code == 200
    assert "Addresses in this range" in response.text
    assert "Host Pair" in response.text
    assert "core" in response.text
    assert "tag-color" in response.text
    assert "10.40.0.11" in response.text
    assert "Add…" in response.text


def test_range_addresses_quick_add_creates_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Edge Range", cidr="10.60.0.0/29")
        project = repository.create_project(connection, name="Edge")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "10.60.0.2", "type": "VM", "project_id": str(project.id)},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/ui/ranges/{ip_range.id}/addresses#ip-10-60-0-2")

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        asset = repository.get_ip_asset_by_ip(connection, "10.60.0.2")
        assert asset is not None
        assert asset.project_id == project.id
    finally:
        connection.close()


def test_range_addresses_allocate_next_free_creates_assets(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Bulk Range", cidr="10.70.0.0/29")
        project = repository.create_project(connection, name="Bulk")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/allocate-next",
            data={"count": "2", "type": "VM", "project_id": str(project.id)},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/ui/ranges/{ip_range.id}/addresses#ip-10-70-0-2")

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        asset_one = repository.get_ip_asset_by_ip(connection, "10.70.0.1")
        asset_two = repository.get_ip_asset_by_ip(connection, "10.70.0.2")
        assert asset_one is not None
        assert asset_two is not None
        assert asset_one.project_id == project.id
        assert asset_two.project_id == project.id
    finally:
        connection.close()


def test_ranges_edit_and_delete_flow(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        edit_response = client.get(f"/ui/ranges/{ip_range.id}/edit")
        assert edit_response.status_code == 200
        assert "Edit IP Range" in edit_response.text

        update_response = client.post(
            f"/ui/ranges/{ip_range.id}/edit",
            data={"name": "Corporate LAN", "cidr": "192.168.20.0/24", "notes": "updated"},
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        delete_confirm = client.get(f"/ui/ranges/{ip_range.id}/delete")
        assert delete_confirm.status_code == 200
        assert "Confirm Range Delete" in delete_confirm.text

        delete_error = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Wrong Name"},
        )
        assert delete_error.status_code == 400
        assert "نام رنج" in delete_error.text

        delete_response = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Corporate LAN"},
            follow_redirects=False,
        )
        assert delete_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_logout_button_hidden_when_not_authenticated(client) -> None:
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "sidebar-logout-button" not in response.text
    assert "sidebar-login-link" in response.text


def test_logout_button_shown_when_authenticated(client, monkeypatch) -> None:
    monkeypatch.setattr(ui, "_is_authenticated_request", lambda request: True)
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "sidebar-logout-button" in response.text
    assert "sidebar-login-link" not in response.text


def test_import_page_includes_sample_csv_links(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "viewer", "x", UserRole.VIEWER, True)
    try:
        response = client.get("/ui/import")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "/static/samples/hosts.csv" in response.text
    assert "/static/samples/ip-assets.csv" in response.text
    assert "Run Nmap" in response.text
    assert "nmap -sn -oX ipocket.xml" in response.text
    assert "nmap -sn -PS80,443 -oX ipocket.xml" in response.text


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


def test_sample_csv_files_are_available(client) -> None:
    hosts_response = client.get("/static/samples/hosts.csv")
    assets_response = client.get("/static/samples/ip-assets.csv")

    assert hosts_response.status_code == 200
    assert assets_response.status_code == 200
    assert "name,notes,vendor_name" in hosts_response.text
    assert "ip_address,type,project_name,host_name,tags,notes,archived" in assets_response.text


def test_ip_asset_form_includes_tags_field_and_prefill(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.70.0.10",
            asset_type=IPAssetType.VM,
            tags=["Prod", "edge"],
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        create_response = client.get("/ui/ip-assets/new")
        edit_response = client.get(f"/ui/ip-assets/{asset.id}/edit")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert create_response.status_code == 200
    assert edit_response.status_code == 200
    assert 'name="tags"' in create_response.text
    assert 'value="edge, prod"' in edit_response.text


def test_tags_page_renders_and_allows_edit_delete(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        tag = repository.create_tag(connection, name="prod", color="#22c55e")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.get("/ui/tags")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 200
    assert 'action="/ui/tags"' in response.text
    assert 'type="color"' in response.text
    assert f'action="/ui/tags/{tag.id}/edit"' in response.text
    assert f'action="/ui/tags/{tag.id}/delete"' in response.text
    assert 'class="card table-card tags-existing-card"' in response.text
    assert 'data-row-actions' in response.text
    assert 'data-row-actions-toggle' in response.text
    assert 'data-row-actions-panel' in response.text
    assert 'class="row-actions-icon"' in response.text
    assert f'aria-controls="row-actions-tag-{tag.id}"' in response.text
    assert "positionMenuPanel" in response.text


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
    assert "bulk-edit-controls-hidden" in response.text
    assert f'aria-controls="row-actions-{asset.id}"' in response.text
    assert f'data-delete-dialog-id="delete-ip-{asset.id}"' in response.text
    assert f'id="delete-ip-{asset.id}"' in response.text
    assert "Delete IP asset?" in response.text
    assert "Continue to delete" in response.text
    assert "window.addEventListener" in response.text
    assert "positionMenuPanel" in response.text


def test_ip_assets_list_htmx_response_renders_table_partial(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(connection, ip_address="10.30.0.12", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    response = client.get("/ui/ip-assets", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert f"/ui/ip-assets/{asset.id}" in response.text
    assert 'data-row-actions' in response.text
    assert "<table" in response.text
    assert "Apply filters" not in response.text


def test_ip_assets_bulk_edit_updates_selected_assets(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        project = repository.create_project(connection, name="Core")
        asset_one = repository.create_ip_asset(
            connection,
            ip_address="10.70.0.10",
            asset_type=IPAssetType.VM,
            tags=["prod"],
        )
        asset_two = repository.create_ip_asset(
            connection,
            ip_address="10.70.0.11",
            asset_type=IPAssetType.OS,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[
                ("asset_ids", str(asset_one.id)),
                ("asset_ids", str(asset_two.id)),
                ("type", "VIP"),
                ("project_id", str(project.id)),
                ("tags", "edge, core"),
                ("return_to", "/ui/ip-assets"),
            ],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    follow_response = client.get(response.headers["location"])
    assert follow_response.status_code == 200
    assert "toast-success" in follow_response.text
    assert "Updated 2 IP assets." in follow_response.text

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        updated_one = repository.get_ip_asset_by_ip(connection, "10.70.0.10")
        updated_two = repository.get_ip_asset_by_ip(connection, "10.70.0.11")
        assert updated_one is not None
        assert updated_two is not None
        assert updated_one.asset_type == IPAssetType.VIP
        assert updated_two.asset_type == IPAssetType.VIP
        assert updated_one.project_id == project.id
        assert updated_two.project_id == project.id
        tag_map = repository.list_tags_for_ip_assets(connection, [asset_one.id, asset_two.id])
        assert tag_map[asset_one.id] == ["core", "edge", "prod"]
        assert tag_map[asset_two.id] == ["core", "edge"]
    finally:
        connection.close()


def test_ip_assets_bulk_edit_shows_error_toast_for_missing_selection(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        repository.create_ip_asset(connection, ip_address="10.70.0.12", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[
                ("type", "VIP"),
                ("return_to", "/ui/ip-assets"),
            ],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    follow_response = client.get(response.headers["location"])
    assert follow_response.status_code == 200
    assert "toast-error" in follow_response.text
    assert "Select at least one IP asset." in follow_response.text


def test_ip_assets_list_renders_project_color_tag(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core", color="#1d4ed8")
        repository.create_ip_asset(
            connection,
            ip_address="10.30.0.11",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
    finally:
        connection.close()

    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert 'class="tag tag-project"' in response.text
    assert "--project-color: #1d4ed8" in response.text
    assert "project-color-dot" not in response.text


def test_hosts_list_renders_project_color_tag(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core", color="#2563eb")
        host = repository.create_host(connection, name="host-01")
        repository.create_ip_asset(
            connection,
            ip_address="10.40.0.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
        )
    finally:
        connection.close()

    response = client.get("/ui/hosts")

    assert response.status_code == 200
    assert 'class="tag tag-project"' in response.text
    assert "--project-color: #2563eb" in response.text
    assert "Core" in response.text


def test_ip_assets_list_search_trims_whitespace(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_asset(connection, ip_address="10.30.0.21", asset_type=IPAssetType.VM)
        repository.create_ip_asset(connection, ip_address="10.30.0.22", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    response = client.get("/ui/ip-assets", params={"q": " 10.30.0.21 "})

    assert response.status_code == 200
    assert "10.30.0.21" in response.text
    assert "10.30.0.22" not in response.text


def test_ip_assets_list_includes_archived_filter(client) -> None:
    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert 'name="archived-only"' in response.text
    assert "Archived only" in response.text


def test_ip_assets_list_paginates_with_default_page_size(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for index in range(25):
            repository.create_ip_asset(
                connection,
                ip_address=f"10.40.0.{index:02d}",
                asset_type=IPAssetType.VM,
            )
    finally:
        connection.close()

    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert "Showing 1-20 of 25" in response.text
    assert "Page 1 of 2" in response.text
    assert "10.40.0.00" in response.text
    assert "10.40.0.20" not in response.text


def test_ip_assets_list_paginates_with_custom_page_size(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for index in range(30):
            repository.create_ip_asset(
                connection,
                ip_address=f"10.50.0.{index:02d}",
                asset_type=IPAssetType.VM,
            )
    finally:
        connection.close()

    response = client.get("/ui/ip-assets", params={"per-page": "10", "page": "2"})

    assert response.status_code == 200
    assert "Showing 11-20 of 30" in response.text
    assert "Page 2 of 3" in response.text
    assert "10.50.0.09" not in response.text
    assert "10.50.0.10" in response.text


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


def test_hosts_add_form_above_table_and_compact(client) -> None:
    response = client.get("/ui/hosts")

    assert response.status_code == 200
    assert 'id="add-host-card"' in response.text
    assert 'class="card compact-card collapsible-card host-add-card"' in response.text
    add_card_index = response.text.find('id="add-host-card"')
    table_index = response.text.find('class="card table-card"')
    assert add_card_index != -1
    assert table_index != -1
    assert add_card_index < table_index


def test_hosts_list_search_trims_whitespace(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_host(connection, name="edge-01", notes="rack-1")
        repository.create_host(connection, name="core-02", notes="rack-2")
    finally:
        connection.close()

    response = client.get("/ui/hosts", params={"q": " edge-01 "})

    assert response.status_code == 200
    assert "edge-01" in response.text
    assert "core-02" not in response.text


def test_audit_log_page_lists_ip_entries(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_asset(connection, ip_address="10.40.0.10", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    response = client.get("/ui/audit-log")

    assert response.status_code == 200
    assert "10.40.0.10" in response.text
    assert "CREATE" in response.text


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
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        asset = repository.create_ip_asset(connection, ip_address="10.20.0.11", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
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
