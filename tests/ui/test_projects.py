from __future__ import annotations

from app import db, repository
from app.main import app
from app.models import IPAssetType, UserRole
from app.routes import ui


def test_projects_page_uses_drawer_actions(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Platform", description="Core workloads")
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.11",
            asset_type=IPAssetType.OTHER,
            project_id=project.id,
        )
    finally:
        connection.close()

    response = client.get("/ui/projects")

    assert response.status_code == 200
    assert "data-project-add" in response.text
    assert "data-project-create-drawer" in response.text
    assert "data-project-edit-drawer" in response.text
    assert "data-project-delete-drawer" in response.text
    assert f'data-project-edit="{project.id}"' in response.text
    assert f'data-project-delete="{project.id}"' in response.text
    assert "<th>IPs</th>" in response.text
    assert ">2</td>" in response.text


def test_projects_edit_and_delete_flow(client) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(connection, username="editor", hashed_password="x", role=UserRole.EDITOR)
        project = repository.create_project(connection, name="Legacy", description="Old")
        repository.create_ip_asset(
            connection,
            ip_address="10.0.10.2",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        edit_redirect = client.get(f"/ui/projects/{project.id}/edit", follow_redirects=False)
        assert edit_redirect.status_code == 303
        assert edit_redirect.headers["location"].endswith(f"/ui/projects?edit={project.id}")

        edited = client.post(
            f"/ui/projects/{project.id}/edit",
            data={"name": "Modern", "description": "New", "color": "#22c55e"},
            follow_redirects=False,
        )
        assert edited.status_code == 303

        delete_redirect = client.get(f"/ui/projects/{project.id}/delete", follow_redirects=False)
        assert delete_redirect.status_code == 303
        assert delete_redirect.headers["location"].endswith(f"/ui/projects?delete={project.id}")

        delete_error = client.post(
            f"/ui/projects/{project.id}/delete",
            data={"confirm_name": "Wrong"},
        )
        assert delete_error.status_code == 400
        assert "Project name confirmation does not match." in delete_error.text
        assert 'data-project-delete-open="true"' in delete_error.text

        deleted = client.post(
            f"/ui/projects/{project.id}/delete",
            data={"confirm_name": "Modern"},
            follow_redirects=False,
        )
        assert deleted.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        assert repository.get_project_by_id(connection, project.id) is None
        asset = repository.get_ip_asset_by_ip(connection, "10.0.10.2")
        assert asset is not None
        assert asset.project_id is None
    finally:
        connection.close()


def test_library_tabs_render_tag_and_vendor_content(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        repository.create_tag(connection, name="critical")
        repository.create_vendor(connection, name="Cisco")
    finally:
        connection.close()

    tags_response = client.get("/ui/projects?tab=tags")
    assert tags_response.status_code == 200
    assert "Catalog Settings" in tags_response.text
    assert 'href="/ui/projects?tab=tags"' in tags_response.text
    assert "data-tag-add" in tags_response.text

    vendors_response = client.get("/ui/projects?tab=vendors")
    assert vendors_response.status_code == 200
    assert "data-vendor-add" in vendors_response.text


def test_tags_route_renders_unified_library_page(client) -> None:
    response = client.get("/ui/tags")

    assert response.status_code == 200
    assert "Catalog Settings" in response.text
    assert "data-tag-add" in response.text


def test_library_page_has_single_header_and_dynamic_primary_action(client) -> None:
    projects_response = client.get("/ui/projects")
    assert projects_response.status_code == 200
    assert projects_response.text.count("<h1>Catalog Settings</h1>") == 1
    assert "<h1>Projects</h1>" not in projects_response.text
    assert "data-project-add" in projects_response.text
    assert "New Project" in projects_response.text

    tags_response = client.get("/ui/projects?tab=tags")
    assert tags_response.status_code == 200
    assert "<h1>Tags</h1>" not in tags_response.text
    assert "data-tag-add" in tags_response.text
    assert "New Tag" in tags_response.text

    vendors_response = client.get("/ui/projects?tab=vendors")
    assert vendors_response.status_code == 200
    assert "<h1>Vendors</h1>" not in vendors_response.text
    assert "data-vendor-add" in vendors_response.text
    assert "New Vendor" in vendors_response.text


def test_library_tabs_are_not_wrapped_in_card_container(client) -> None:
    response = client.get("/ui/projects")
    assert response.status_code == 200
    tabs_index = response.text.index('class="tabs" role="tablist"')
    first_table_card_index = response.text.index('class="card table-card')
    assert tabs_index < first_table_card_index
    assert '<section class="card" style="margin-bottom: 16px;">' not in response.text
