from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


def test_ranges_page_renders_single_combined_ranges_table(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
    finally:
        connection.close()

    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert "data-range-add" in response.text
    assert "Add IP Range" in response.text
    assert "data-range-create-drawer" in response.text
    assert "192.168.10.0/24" in response.text
    assert "Saved ranges" not in response.text
    assert "Subnet Utilization" not in response.text
    assert "<h2>IP Ranges</h2>" in response.text
    assert "Total usable" in response.text
    assert "Used" in response.text
    assert "Free" in response.text
    assert "Utilization" in response.text
    assert "Actions" in response.text
    assert "Created" not in response.text
    assert f'href="/ui/ranges/{ip_range.id}/addresses#used"' in response.text
    assert f'href="/ui/ranges/{ip_range.id}/addresses#free"' in response.text
    assert 'class="btn btn-secondary btn-small"' in response.text
    assert 'class="btn btn-danger btn-small"' in response.text
    assert "data-range-edit" in response.text
    assert "data-range-delete" in response.text
    assert "data-range-delete-cidr=\"192.168.10.0/24\"" in response.text
    assert "data-range-delete-cidr-display" in response.text
    assert "data-range-delete-used-display" in response.text
    assert "data-range-delete-drawer" in response.text



def test_ranges_page_shows_em_dash_when_utilization_missing(client, monkeypatch) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_range(connection, name="No Util", cidr="10.10.10.0/30")
    finally:
        connection.close()

    from app.routes.ui import ranges as ranges_ui

    monkeypatch.setattr(ranges_ui.repository, "get_ip_range_utilization", lambda _connection: [])

    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert "No Util" in response.text
    assert "—" in response.text

def test_ranges_page_reopens_create_drawer_with_errors(client) -> None:
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
            "/ui/ranges",
            data={"name": "", "cidr": "", "notes": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Range name is required." in response.text
    assert "CIDR is required." in response.text
    assert 'data-range-open="true"' in response.text

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
    assert "Edit" in response.text
    assert "data-range-drawer" in response.text
    assert "data-tag-picker" in response.text
    assert "Allocate next" not in response.text

def test_range_addresses_quick_add_creates_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Edge Range", cidr="10.60.0.0/29")
        project = repository.create_project(connection, name="Edge")
        repository.create_tag(connection, name="edge")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": "10.60.0.2",
                "type": "VM",
                "project_id": str(project.id),
                "notes": "allocated from range",
                "tags": ["edge"],
            },
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
        assert asset.notes == "allocated from range"
        assert repository.list_tags_for_ip_assets(connection, [asset.id])[asset.id] == ["edge"]
    finally:
        connection.close()

def test_range_addresses_quick_edit_updates_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Edge Range", cidr="10.61.0.0/29")
        project = repository.create_project(connection, name="Core")
        repository.create_tag(connection, name="mgmt")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.61.0.2",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{asset.id}/edit",
            data={"type": "BMC", "project_id": str(project.id), "notes": "updated", "tags": ["mgmt"]},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/ui/ranges/{ip_range.id}/addresses#ip-10-61-0-2")

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        updated = repository.get_ip_asset_by_ip(connection, "10.61.0.2")
        assert updated is not None
        assert updated.asset_type == IPAssetType.BMC
        assert updated.project_id == project.id
        assert updated.notes == "updated"
        assert repository.list_tags_for_ip_assets(connection, [updated.id])[updated.id] == ["mgmt"]
    finally:
        connection.close()


def test_range_addresses_quick_add_rejects_nonexistent_tag_selection(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Fail Range", cidr="10.62.0.0/29")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": "10.62.0.2",
                "type": "VM",
                "project_id": "",
                "notes": "",
                "tags": "ghost",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Selected tags do not exist: ghost." in response.text

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
        edit_response = client.get(f"/ui/ranges/{ip_range.id}/edit", follow_redirects=False)
        assert edit_response.status_code == 303
        assert edit_response.headers["location"].endswith(f"/ui/ranges?edit={ip_range.id}")

        update_response = client.post(
            f"/ui/ranges/{ip_range.id}/edit",
            data={"name": "Corporate LAN", "cidr": "192.168.20.0/24", "notes": "updated"},
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        delete_confirm = client.get(f"/ui/ranges/{ip_range.id}/delete", follow_redirects=False)
        assert delete_confirm.status_code == 303
        assert delete_confirm.headers["location"].endswith(f"/ui/ranges?delete={ip_range.id}")

        delete_drawer = client.get(f"/ui/ranges?delete={ip_range.id}")
        assert delete_drawer.status_code == 200
        assert 'data-range-delete-open="true"' in delete_drawer.text
        assert f'action="/ui/ranges/{ip_range.id}/delete"' in delete_drawer.text

        delete_error = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Wrong Name"},
        )
        assert delete_error.status_code == 400
        assert "نام رنج" in delete_error.text
        assert 'data-range-delete-open="true"' in delete_error.text

        delete_response = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Corporate LAN"},
            follow_redirects=False,
        )
        assert delete_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_ranges_page_opens_delete_drawer_from_query_param(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(connection, name="Delete Me", cidr="10.30.0.0/24")
    finally:
        connection.close()

    response = client.get(f"/ui/ranges?delete={ip_range.id}")

    assert response.status_code == 200
    assert 'data-range-delete-drawer' in response.text
    assert 'data-range-delete-open="true"' in response.text
    assert f'data-range-delete-id="{ip_range.id}"' in response.text
    assert f'action="/ui/ranges/{ip_range.id}/delete"' in response.text


def test_ranges_page_opens_edit_drawer_from_query_param(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24", notes="initial")
    finally:
        connection.close()

    response = client.get(f"/ui/ranges?edit={ip_range.id}")

    assert response.status_code == 200
    assert 'data-range-edit-drawer' in response.text
    assert f'data-range-edit-id="{ip_range.id}"' in response.text
    assert f'action="/ui/ranges/{ip_range.id}/edit"' in response.text
    assert 'value="Corp LAN"' in response.text


def test_range_edit_error_reopens_edit_drawer(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        ip_range = repository.create_ip_range(connection, name="Corp LAN", cidr="192.168.10.0/24")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/edit",
            data={"name": "", "cidr": "", "notes": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert 'Range name is required.' in response.text
    assert 'CIDR is required.' in response.text
    assert 'data-range-edit-open="true"' in response.text
