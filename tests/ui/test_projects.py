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
