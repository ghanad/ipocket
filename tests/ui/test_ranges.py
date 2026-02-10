from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


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
    assert "data-range-add" in response.text
    assert "Add IP Range" in response.text
    assert "data-range-create-drawer" in response.text
    assert "192.168.10.0/24" in response.text
    assert "Saved ranges" in response.text
    assert "data-row-actions" in response.text



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
                "tags": "edge",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/ui/ranges/{ip_range.id}/addresses")

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
            data={"type": "BMC", "project_id": str(project.id), "notes": "updated", "tags": "mgmt"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/ui/ranges/{ip_range.id}/addresses")

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

