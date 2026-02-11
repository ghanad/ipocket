from __future__ import annotations

import re
from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


def test_ip_assets_drawer_auto_host_creates_and_assigns(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.70.0.5",
            asset_type=IPAssetType.BMC,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(f"/ui/ip-assets/{asset.id}/auto-host")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["host_name"] == "server_10.70.0.5"

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        updated = repository.get_ip_asset_by_ip(connection, "10.70.0.5")
        assert updated is not None
        assert updated.host_id == payload["host_id"]
        host = repository.get_host_by_id(connection, payload["host_id"])
        assert host is not None
        assert host.name == "server_10.70.0.5"
    finally:
        connection.close()

def test_ip_assets_drawer_auto_host_rejects_assigned_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        host = repository.create_host(connection, name="edge-02")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.70.0.6",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(f"/ui/ip-assets/{asset.id}/auto-host")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"] == "This IP is already assigned to a host."

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
        repository.create_tag(connection, name="prod")
        repository.create_tag(connection, name="edge")
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
    assert 'name="tags" multiple' in create_response.text
    assert 'data-tag-picker' in create_response.text
    assert re.search(r'<option value="edge"[^>]*selected', edit_response.text)
    assert re.search(r'<option value="prod"[^>]*selected', edit_response.text)

def test_tags_page_uses_drawers_for_create_edit_delete(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        tag = repository.create_tag(connection, name="prod", color="#22c55e")
        repository.create_ip_asset(
            connection,
            ip_address="10.200.0.10",
            asset_type=IPAssetType.VM,
            tags=["prod"],
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.get("/ui/tags")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 200
    assert 'data-tag-add' in response.text
    assert 'type="button" data-tag-add' in response.text
    assert 'data-tag-create-drawer' in response.text
    assert 'data-tag-edit-drawer' in response.text
    assert 'data-tag-delete-drawer' in response.text
    assert 'action="/ui/tags"' in response.text
    assert 'type="color"' in response.text
    assert f'data-tag-edit="{tag.id}"' in response.text
    assert 'type="button"' in response.text
    assert f'data-tag-delete="{tag.id}"' in response.text
    assert f'data-tag-delete-name="{tag.name}"' in response.text
    assert f'data-tag-name="{tag.name}"' in response.text
    assert f'data-tag-color="{tag.color}"' in response.text
    assert "<th>IPs</th>" in response.text
    assert ">1</td>" in response.text
    tags_js = Path(__file__).resolve().parents[2] / "app/static/js/tags.js"
    tags_js_content = tags_js.read_text(encoding="utf-8")
    assert "data-tag-create-overlay" in tags_js_content
    assert "data-tag-edit-overlay" in tags_js_content
    assert "data-tag-delete-overlay" in tags_js_content
    assert '/static/js/tags.js' in response.text
    assert '/static/js/drawer.js' in response.text
    assert 'class="card table-card tags-existing-card"' in response.text
def test_tag_delete_requires_exact_name_confirmation(client) -> None:
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
        response = client.post(f"/ui/tags/{tag.id}/delete", data={"confirm_name": "wrong"})
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Tag name confirmation does not match." in response.text
    assert f'action="/ui/tags/{tag.id}/delete"' in response.text

def test_ip_assets_list_uses_drawer_actions_for_edit_and_delete(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        host = repository.create_host(connection, name="edge-01")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.30.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
            tags=["edge"],
            notes="Primary",
        )
    finally:
        connection.close()

    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert "bulk-edit-controls-hidden" in response.text
    assert f'data-ip-edit="{asset.id}"' in response.text
    assert 'data-ip-address="10.30.0.10"' in response.text
    assert 'data-ip-type="VM"' in response.text
    assert f'data-ip-project-id="{project.id}"' in response.text
    assert f'data-ip-host-id="{host.id}"' in response.text
    assert 'data-ip-tags="edge"' in response.text
    assert 'data-ip-notes="Primary"' in response.text
    assert f'data-ip-delete="{asset.id}"' in response.text
    assert 'data-ip-delete-form' in response.text
    assert 'data-ip-drawer-mode="edit"' in response.text
    assert 'data-ip-mode-panel="edit"' in response.text
    assert 'data-ip-mode-panel="delete"' in response.text
    assert 'data-ip-mode-action="edit"' in response.text
    assert 'data-ip-mode-action="delete"' in response.text
    assert 'Delete permanently' in response.text
    assert 'I understand this cannot be undone' in response.text
    assert "data-ip-add" in response.text
    assert "data-ip-drawer" in response.text
    assert "Save changes" in response.text
    ip_assets_js = Path(__file__).resolve().parents[2] / "app/static/js/ip-assets.js"
    js_source = ip_assets_js.read_text(encoding="utf-8")
    assert "ipocket.ip-assets.scrollY" in js_source
    assert "drawer.dataset.ipDrawerMode = normalizedMode" in js_source
    assert "form.style.display = isDeleteMode ? 'none' : 'flex'" in js_source
    assert "deleteForm.style.display = isDeleteMode ? 'flex' : 'none'" in js_source
    assert "data-ip-drawer-title" in response.text
    assert "Save" in response.text
    assert "/static/js/ip-assets.js" in response.text
    assert "data-ip-host-field" in response.text
    assert "data-tag-picker" in response.text



def test_ip_assets_list_collapses_tag_chips_and_renders_more_popover_trigger(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_asset(
            connection,
            ip_address="10.30.0.21",
            asset_type=IPAssetType.VM,
            tags=["alpha", "beta", "gamma", "delta", "epsilon"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.30.0.22",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    response = client.get("/ui/ip-assets")

    assert response.status_code == 200
    assert 'data-tags-more-toggle' in response.text
    assert 'data-tags-ip="10.30.0.21"' in response.text
    assert '+2 more' in response.text
    assert 'aria-label="Tags for 10.30.0.21"' in response.text
    assert '<td class="ip-tags-cell">' in response.text
    assert response.text.count('<span class="muted">—</span>') >= 1
    ip_assets_js = Path(__file__).resolve().parents[2] / "app/static/js/ip-assets.js"
    js_source = ip_assets_js.read_text(encoding="utf-8")
    assert "data-tags-popover-search" in js_source
    assert "data-tags-more-toggle" in js_source
    assert "closeTagsPopover" in js_source

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
    assert 'data-ip-edit' in response.text
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
        repository.create_tag(connection, name="edge")
        repository.create_tag(connection, name="core")
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
                ("tags", "edge"),
                ("tags", "core"),
                ("return_to", "/ui/ip-assets"),
            ],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/ip-assets?")
    assert "bulk-success=Updated+2+IP+assets." in response.headers["location"]
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

def test_ip_assets_edit_returns_to_list_when_return_to_set(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.90.0.10",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ip-assets/{asset.id}/edit",
            data={
                "type": "VIP",
                "project_id": "",
                "host_id": "",
                "tags": "",
                "notes": "",
                "return_to": "/ui/ip-assets?archived-only=false",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/ip-assets?archived-only=false"

def test_ip_assets_create_returns_to_list_when_return_to_set(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ip-assets/new",
            data={
                "ip_address": "10.90.0.20",
                "type": "VM",
                "project_id": "",
                "host_id": "",
                "tags": "",
                "notes": "",
                "return_to": "/ui/ip-assets?q=10.90",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/ip-assets?q=10.90"

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


def test_ip_assets_create_rejects_nonexistent_tag_selection(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ip-assets/new",
            data={
                "ip_address": "10.90.0.30",
                "type": "VM",
                "project_id": "",
                "host_id": "",
                "tags": "ghost",
                "notes": "",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Selected tags do not exist: ghost." in response.text


def test_ip_assets_bulk_edit_rejects_nonexistent_tag_selection(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        asset = repository.create_ip_asset(connection, ip_address="10.70.0.55", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[
                ("asset_ids", str(asset.id)),
                ("tags", "ghost"),
                ("return_to", "/ui/ip-assets"),
            ],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    follow_response = client.get(response.headers["location"])
    assert follow_response.status_code == 200
    assert "Selected tags do not exist: ghost." in follow_response.text

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
    assert 'class="tag tag-project tag-filter-chip"' in response.text
    assert "--project-color: #1d4ed8" in response.text
    assert "project-color-dot" not in response.text

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

def test_ip_assets_list_supports_multi_tag_filter_and_clickable_filter_chips(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Chook")
        repository.create_ip_asset(
            connection,
            ip_address="10.31.0.21",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            tags=["prod"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.31.0.22",
            asset_type=IPAssetType.OS,
            tags=["edge"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.31.0.23",
            asset_type=IPAssetType.OS,
            tags=["ops"],
        )
    finally:
        connection.close()

    list_response = client.get("/ui/ip-assets")
    filtered_response = client.get("/ui/ip-assets", params=[("tag", "prod"), ("tag", "edge")])

    assert list_response.status_code == 200
    assert 'name="tag"' not in list_response.text
    assert 'data-tag-filter-selected' in list_response.text
    assert 'data-tag-filter-input' in list_response.text
    assert 'tag-filter-suggestions' in list_response.text
    assert '<span>Tags</span>' in list_response.text
    assert list_response.text.index('name="archived-only"') < list_response.text.index('data-tag-filter-input')
    assert f'data-quick-filter-value="{project.id}"' in list_response.text
    assert 'data-quick-filter="type"' in list_response.text
    assert 'data-quick-filter="tag"' in list_response.text
    assert filtered_response.status_code == 200
    assert "10.31.0.21" in filtered_response.text
    assert "10.31.0.22" in filtered_response.text
    assert "10.31.0.23" not in filtered_response.text

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

def test_ip_asset_detail_page_requires_authentication(client) -> None:
    """Unauthenticated users should be redirected to login page for IP asset detail."""
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(connection, ip_address="10.50.0.99", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    response = client.get(f"/ui/ip-assets/{asset.id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["Location"] == f"/ui/login?return_to=/ui/ip-assets/{asset.id}"

def test_ui_delete_ip_asset_requires_checkbox_confirmation(client) -> None:
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
        response = client.post(
            f"/ui/ip-assets/{asset.id}/delete",
            data={"confirm_ip": "", "confirm_delete_ack": ""},
            headers={"Accept": "application/json"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert response.json()["error"] == "Confirm that this delete cannot be undone."

def test_ui_delete_ip_asset_with_low_risk_confirmation_checkbox_only(client) -> None:
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
            files={
                "confirm_delete_ack": (None, "on"),
                "confirm_ip": (None, ""),
                "return_to": (None, "/ui/ip-assets"),
            },
            headers={"Accept": "application/json"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 200
    assert response.json()["ip_address"] == "10.20.0.11"

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        deleted = repository.get_ip_asset_by_ip(connection, "10.20.0.11")
    finally:
        connection.close()

    assert deleted is None



def test_ui_delete_high_risk_ip_asset_requires_exact_ip(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        project = repository.create_project(connection, name="Prod")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.20.0.21",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        invalid_response = client.post(
            f"/ui/ip-assets/{asset.id}/delete",
            data={"confirm_delete_ack": "on", "confirm_ip": "10.20.0.99"},
            headers={"Accept": "application/json"},
        )
        valid_response = client.post(
            f"/ui/ip-assets/{asset.id}/delete",
            data={"confirm_delete_ack": "on", "confirm_ip": "10.20.0.21"},
            headers={"Accept": "application/json"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert invalid_response.status_code == 400
    assert invalid_response.json()["error"] == "Type the exact IP address to delete this high-risk asset."
    assert valid_response.status_code == 200

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

def test_ip_asset_detail_uses_enhanced_layout_and_delete_drawer(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="viewer", hashed_password="x", role=UserRole.VIEWER)
        project = repository.create_project(connection, name="Platform", color="#22c55e")
        host = repository.create_host(connection, name="node-10")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.90.0.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
            tags=["core"],
            notes="Primary node",
            current_user=user,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.get(f"/ui/ip-assets/{asset.id}")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "<h2>Details</h2>" in response.text
    assert "Status: Assigned" in response.text
    assert 'data-ip-delete="' in response.text
    assert 'data-ip-drawer-mode="delete"' in response.text
    assert 'data-ip-delete-form' in response.text
    assert '/static/js/ip-assets.js' in response.text
    assert 'class="pill pill-success"' in response.text
    assert "Type: OS; Project ID:" in response.text
    assert "View details" in response.text


def test_ip_asset_detail_shows_no_tags_and_no_notes_defaults(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="viewer2", hashed_password="x", role=UserRole.VIEWER)
        asset = repository.create_ip_asset(connection, ip_address="10.90.0.11", asset_type=IPAssetType.VM)
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.get(f"/ui/ip-assets/{asset.id}")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "No tags" in response.text
    assert "No notes" in response.text
    assert "Status: Needs assignment" in response.text
