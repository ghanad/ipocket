from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


def test_hosts_page_renders_edit_drawer_and_actions(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        vendor = repository.create_vendor(connection, name="Dell")
        host = repository.create_host(connection, name="edge-01", vendor=vendor.name, notes="rack-a")
        repository.create_ip_asset(
            connection,
            ip_address="10.50.0.10",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.50.0.11",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()

    response = client.get("/ui/hosts")

    assert response.status_code == 200
    assert 'data-host-edit="' in response.text
    assert f'data-host-delete="{host.id}"' in response.text
    assert "Edit Host" in response.text
    assert "Save changes" in response.text
    assert "host-edit-row-" not in response.text

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

def test_hosts_list_uses_edit_drawer_actions(client) -> None:
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
    assert f'data-host-edit="{host.id}"' in response.text
    assert f'data-host-name="{host.name}"' in response.text
    assert f'data-host-delete="{host.id}"' in response.text
    assert 'data-host-project-count="0"' in response.text
    assert 'name="project_id"' in response.text
    assert "data-host-drawer" in response.text
    assert "Save changes" in response.text

def test_hosts_add_uses_side_panel(client) -> None:
    """Test that Add Host uses the side panel drawer instead of inline form."""
    response = client.get("/ui/hosts")

    assert response.status_code == 200
    # Should have the "New Host" button in page header
    assert "data-host-add" in response.text
    assert "New Host" in response.text
    # Should have the drawer that can be used for both Add and Edit
    assert "data-host-drawer" in response.text
    # Should have "Create Host" button text in the drawer (set by JS)
    # The drawer title is dynamically set by JS, but the form action should be /ui/hosts for add
    assert 'formaction="/ui/hosts"' in response.text or 'action="/ui/hosts"' in response.text
    # Should NOT have the old inline add form
    assert 'id="add-host-card"' not in response.text

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

def test_hosts_list_paginates_with_default_page_size(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for i in range(25):
            repository.create_host(connection, name=f"host-{i:03d}")
    finally:
        connection.close()

    response = client.get("/ui/hosts")

    assert response.status_code == 200
    assert "host-000" in response.text
    assert "host-019" in response.text
    assert "host-020" not in response.text
    assert "Page 1 of 2" in response.text
    assert "Showing 1-20 of 25" in response.text

def test_hosts_list_paginates_with_custom_page_size(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for i in range(15):
            repository.create_host(connection, name=f"host-{i:03d}")
    finally:
        connection.close()

    response = client.get("/ui/hosts", params={"per-page": "10"})

    assert response.status_code == 200
    assert "host-000" in response.text
    assert "host-009" in response.text
    assert "host-010" not in response.text
    assert "Page 1 of 2" in response.text
    assert "Showing 1-10 of 15" in response.text

def test_hosts_list_pagination_with_search(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for i in range(25):
            repository.create_host(connection, name=f"server-{i:03d}")
        repository.create_host(connection, name="special-host")
    finally:
        connection.close()

    response = client.get("/ui/hosts", params={"q": "server", "per-page": "10"})

    assert response.status_code == 200
    assert "server-000" in response.text
    assert "special-host" not in response.text
    assert "Page 1 of 3" in response.text
    assert "Showing 1-10 of 25" in response.text

def test_hosts_list_pagination_navigation(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        for i in range(30):
            repository.create_host(connection, name=f"host-{i:03d}")
    finally:
        connection.close()

    response = client.get("/ui/hosts", params={"page": "2", "per-page": "10"})

    assert response.status_code == 200
    assert "host-000" not in response.text
    assert "host-010" in response.text
    assert "host-019" in response.text
    assert "host-020" not in response.text
    assert "Page 2 of 3" in response.text
    assert "Showing 11-20 of 30" in response.text

def test_hosts_edit_updates_project_assignments(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        host = repository.create_host(connection, name="edge-01")
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.10",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
    finally:
        connection.close()

    from app.models import User
    from app.routes import ui

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={"name": "edge-01", "project_id": str(project.id)},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        asset = repository.get_ip_asset_by_ip(connection, "10.20.0.10")
        assert asset is not None
        assert asset.project_id == project.id
    finally:
        connection.close()

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

def test_ui_create_host_with_os_and_bmc_ips(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            "/ui/hosts",
            data={
                "name": "edge-02",
                "notes": "new host",
                "os_ips": "10.10.0.10, 10.10.0.11",
                "bmc_ips": "10.10.0.20",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        host = repository.get_host_by_name(connection, "edge-02")
        os_asset = repository.get_ip_asset_by_ip(connection, "10.10.0.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.10.0.20")
    finally:
        connection.close()

    assert host is not None
    assert os_asset is not None
    assert bmc_asset is not None
    assert os_asset.asset_type == IPAssetType.OS
    assert bmc_asset.asset_type == IPAssetType.BMC
    assert os_asset.host_id == host.id
    assert bmc_asset.host_id == host.id

def test_ui_create_host_with_project_assigns_linked_ips(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            "/ui/hosts",
            data={
                "name": "edge-02-with-project",
                "project_id": str(project.id),
                "os_ips": "10.10.2.10",
                "bmc_ips": "10.10.2.20",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        os_asset = repository.get_ip_asset_by_ip(connection, "10.10.2.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.10.2.20")
    finally:
        connection.close()

    assert os_asset is not None
    assert bmc_asset is not None
    assert os_asset.project_id == project.id
    assert bmc_asset.project_id == project.id

def test_ui_edit_host_adds_os_and_bmc_ips(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="edge-03")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={"name": "edge-03", "notes": "", "os_ips": "10.10.1.10", "bmc_ips": "10.10.1.20"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        os_asset = repository.get_ip_asset_by_ip(connection, "10.10.1.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.10.1.20")
    finally:
        connection.close()

    assert os_asset is not None
    assert bmc_asset is not None
    assert os_asset.asset_type == IPAssetType.OS
    assert bmc_asset.asset_type == IPAssetType.BMC
    assert os_asset.host_id == host.id
    assert bmc_asset.host_id == host.id

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

    assert form_response.status_code == 303
    assert form_response.headers.get("location", "").endswith(f"/ui/hosts?delete={host.id}")
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

def test_ui_delete_host_allows_when_linked_ips_exist_and_unlinks_ips(client) -> None:
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

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        deleted_host = repository.get_host_by_id(connection, host.id)
        linked_asset = repository.get_ip_asset_by_ip(connection, "10.20.0.31")
    finally:
        connection.close()

    assert deleted_host is None
    assert linked_asset is not None
    assert linked_asset.host_id is None

def test_ui_create_host_links_existing_ips(client) -> None:
    """Test that creating a host with existing IPs links them instead of throwing an error."""
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        # Create existing IP assets without a host
        existing_os = repository.create_ip_asset(
            connection, ip_address="10.30.0.10", asset_type=IPAssetType.OS
        )
        existing_bmc = repository.create_ip_asset(
            connection, ip_address="10.30.0.20", asset_type=IPAssetType.BMC
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            "/ui/hosts",
            data={
                "name": "edge-existing-ips",
                "notes": "host with existing IPs",
                "os_ips": "10.30.0.10",  # Existing IP
                "bmc_ips": "10.30.0.20",  # Existing IP
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        host = repository.get_host_by_name(connection, "edge-existing-ips")
        os_asset = repository.get_ip_asset_by_ip(connection, "10.30.0.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.30.0.20")
    finally:
        connection.close()

    assert host is not None
    assert os_asset is not None
    assert bmc_asset is not None
    # IPs should now be linked to the new host
    assert os_asset.host_id == host.id
    assert bmc_asset.host_id == host.id

def test_ui_edit_host_links_existing_ips(client) -> None:
    """Test that editing a host to add existing IPs links them instead of throwing an error."""
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="edge-edit-existing")
        # Create existing IP assets without a host
        existing_os = repository.create_ip_asset(
            connection, ip_address="10.40.0.10", asset_type=IPAssetType.OS
        )
        existing_bmc = repository.create_ip_asset(
            connection, ip_address="10.40.0.20", asset_type=IPAssetType.BMC
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={
                "name": "edge-edit-existing",
                "notes": "",
                "os_ips": "10.40.0.10",  # Existing IP
                "bmc_ips": "10.40.0.20",  # Existing IP
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        os_asset = repository.get_ip_asset_by_ip(connection, "10.40.0.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.40.0.20")
    finally:
        connection.close()

    assert os_asset is not None
    assert bmc_asset is not None
    # IPs should now be linked to the host
    assert os_asset.host_id == host.id
    assert bmc_asset.host_id == host.id


def test_ui_edit_host_unlinks_removed_os_and_bmc_ips(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="edge-edit-unlink")
        repository.create_ip_asset(
            connection,
            ip_address="10.41.0.10",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.41.0.20",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/edit",
            data={
                "name": "edge-edit-unlink",
                "notes": "",
                "os_ips": "",
                "bmc_ips": "",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        os_asset = repository.get_ip_asset_by_ip(connection, "10.41.0.10")
        bmc_asset = repository.get_ip_asset_by_ip(connection, "10.41.0.20")
    finally:
        connection.close()

    assert os_asset is not None
    assert bmc_asset is not None
    assert os_asset.host_id is None
    assert bmc_asset.host_id is None


def test_ui_delete_host_open_delete_redirect_shows_drawer(client) -> None:
    """Test that opening host delete redirects to hosts page with delete drawer open."""
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-cancel-test", notes="temp")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.get(f"/ui/hosts/{host.id}/delete")
        list_response = client.get(f"/ui/hosts?delete={host.id}")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers.get("location", "").endswith(f"/ui/hosts?delete={host.id}")
    assert list_response.status_code == 200
    assert 'data-host-delete-open="true"' in list_response.text
    assert f'data-host-delete-id="{host.id}"' in list_response.text
    assert "data-host-delete-linked-value" in list_response.text
    assert 'data-host-mode-panel="delete"' in list_response.text
    assert "Delete permanently" in list_response.text


def test_ui_delete_host_shows_success_flash_message(client) -> None:
    """Test that successful deletion sets a flash message cookie."""
    import os
    from app import db, repository
    from app.routes.ui.utils import FLASH_COOKIE

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        host = repository.create_host(connection, name="node-flash-test", notes="temp")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: User(1, "editor", "x", UserRole.EDITOR, True)
    try:
        response = client.post(
            f"/ui/hosts/{host.id}/delete",
            data={"confirm_name": "node-flash-test"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    # Redirect should go to hosts list
    location = response.headers.get("location", "")
    assert "/ui/hosts" in location
    # Flash message should be set in cookie (via Set-Cookie header)
    set_cookie = response.headers.get("set-cookie", "")
    assert FLASH_COOKIE in set_cookie
