from __future__ import annotations

from app import repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from app.routes.ui.settings import api as library_api


def _editor() -> User:
    return User(1, "editor", "x", UserRole.EDITOR, True)


def test_ui_library_api_lists_only_react_data_and_usage_counts(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        project = repository.create_project(
            connection,
            name="Platform",
            description="Core",
            color="#123ABC",
        )
        vendor = repository.create_vendor(connection, name="Cisco")
        tag = repository.create_tag(connection, name="prod", color="#22C55E")
        host = repository.create_host(connection, name="node-1", vendor=vendor.name)
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.20.0.10",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            host_id=host.id,
        )
        repository.set_ip_asset_tags(connection, asset.id, ["prod"])
    finally:
        connection.close()

    monkeypatch.setattr(library_api, "suggest_random_tag_color", lambda: "#abcdef")
    app.dependency_overrides[ui.get_current_ui_user] = _editor
    try:
        projects = client.get("/api/ui/library/projects")
        vendors = client.get("/api/ui/library/vendors")
        tags = client.get("/api/ui/library/tags")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert projects.status_code == 200
    assert projects.json() == {
        "items": [
            {
                "id": project.id,
                "name": "Platform",
                "description": "Core",
                "color": "#123ABC",
                "usage_count": 1,
            }
        ],
        "can_edit": True,
        "default_color": "#94a3b8",
    }
    assert vendors.json()["items"] == [
        {"id": vendor.id, "name": "Cisco", "usage_count": 1}
    ]
    assert tags.json() == {
        "items": [
            {
                "id": tag.id,
                "name": "prod",
                "color": "#22c55e",
                "usage_count": 1,
            }
        ],
        "can_edit": True,
        "suggested_color": "#abcdef",
        "default_color": "#e2e8f0",
    }


def test_ui_library_api_crud_validation_and_exact_delete_confirmation(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(library_api, "suggest_random_tag_color", lambda: "#123abc")
    app.dependency_overrides[ui.get_current_ui_user] = _editor
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        project = client.post(
            "/api/ui/library/projects",
            json={
                "name": "  Platform  ",
                "description": "  Core workloads  ",
                "color": "#AABBCC",
            },
        )
        assert project.status_code == 201
        assert project.json()["name"] == "Platform"
        assert project.json()["description"] == "Core workloads"
        assert project.json()["color"] == "#aabbcc"
        project_id = project.json()["id"]

        duplicate_project = client.post(
            "/api/ui/library/projects",
            json={"name": "Platform", "description": "", "color": "#aabbcc"},
        )
        assert duplicate_project.status_code == 409
        invalid_project = client.post(
            "/api/ui/library/projects",
            json={"name": " ", "description": "", "color": "invalid"},
        )
        assert invalid_project.status_code == 422
        project_messages = [item["msg"] for item in invalid_project.json()["detail"]]
        assert any("Project name is required." in item for item in project_messages)
        assert any("Project color must be" in item for item in project_messages)

        updated_project = client.patch(
            f"/api/ui/library/projects/{project_id}",
            json={"name": "Platform 2", "description": "", "color": ""},
        )
        assert updated_project.status_code == 200
        assert updated_project.json()["description"] == "Core workloads"
        assert updated_project.json()["color"] == "#94a3b8"

        vendor = client.post(
            "/api/ui/library/vendors",
            json={"name": "  Cisco  "},
        )
        assert vendor.status_code == 201
        vendor_id = vendor.json()["id"]
        assert client.post(
            "/api/ui/library/vendors", json={"name": "Cisco"}
        ).status_code == 409
        assert client.patch(
            f"/api/ui/library/vendors/{vendor_id}", json={"name": "Juniper"}
        ).json()["name"] == "Juniper"

        tag = client.post(
            "/api/ui/library/tags",
            json={"name": " PROD ", "color": ""},
        )
        assert tag.status_code == 201
        assert tag.json()["name"] == "prod"
        assert tag.json()["color"] == "#123abc"
        tag_id = tag.json()["id"]
        invalid_tag = client.patch(
            f"/api/ui/library/tags/{tag_id}",
            json={"name": "bad name", "color": "#22c55e"},
        )
        assert invalid_tag.status_code == 422
        assert "Tag name may include" in invalid_tag.json()["detail"][0]["msg"]
        updated_tag = client.patch(
            f"/api/ui/library/tags/{tag_id}",
            json={"name": "edge", "color": "#ABCDEF"},
        )
        assert updated_tag.json()["color"] == "#abcdef"

        for entity, entity_id, name in (
            ("projects", project_id, "Platform 2"),
            ("vendors", vendor_id, "Juniper"),
            ("tags", tag_id, "edge"),
        ):
            mismatch = client.request(
                "DELETE",
                f"/api/ui/library/{entity}/{entity_id}",
                json={"confirm_name": "wrong"},
            )
            assert mismatch.status_code == 400
            deleted = client.request(
                "DELETE",
                f"/api/ui/library/{entity}/{entity_id}",
                json={"confirm_name": name},
            )
            assert deleted.status_code == 204
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
        app.dependency_overrides.pop(ui.require_ui_editor, None)


def test_ui_library_api_preserves_session_auth_and_role_rules(
    client, _create_user
) -> None:
    unauthenticated = client.get(
        "/api/ui/library/projects", follow_redirects=False
    )
    assert unauthenticated.status_code == 303
    assert "/ui/login?return_to=/api/ui/library/projects" in unauthenticated.headers[
        "location"
    ]

    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    viewer_login = client.post(
        "/ui/login",
        data={
            "username": "viewer",
            "password": "viewer-pass",
            "return_to": "/ui/projects",
        },
        follow_redirects=False,
    )
    assert viewer_login.status_code == 303
    viewer_list = client.get("/api/ui/library/projects")
    assert viewer_list.status_code == 200
    assert viewer_list.json()["can_edit"] is False
    assert (
        client.post(
            "/api/ui/library/projects",
            json={"name": "Forbidden", "description": "", "color": "#123abc"},
        ).status_code
        == 403
    )

    _create_user("admin", "admin-pass", UserRole.SUPERUSER)
    admin_login = client.post(
        "/ui/login",
        data={
            "username": "admin",
            "password": "admin-pass",
            "return_to": "/ui/projects",
        },
        follow_redirects=False,
    )
    assert admin_login.status_code == 303
    assert client.get("/api/ui/library/vendors").json()["can_edit"] is False
    assert (
        client.post("/api/ui/library/vendors", json={"name": "Forbidden"}).status_code
        == 403
    )

    _create_user("editor", "editor-pass", UserRole.EDITOR)
    editor_login = client.post(
        "/ui/login",
        data={
            "username": "editor",
            "password": "editor-pass",
            "return_to": "/ui/projects",
        },
        follow_redirects=False,
    )
    assert editor_login.status_code == 303
    created = client.post(
        "/api/ui/library/vendors",
        json={"name": "Allowed"},
    )
    assert created.status_code == 201


def test_ui_library_legacy_error_response_bootstraps_react_drawer(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor-bootstrap",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        vendor = repository.create_vendor(connection, name="Cisco")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/vendors/{vendor.id}/edit",
            data={"name": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert 'id="library-root"' in response.text
    assert '"tab": "vendors"' in response.text
    assert '"mode": "edit"' in response.text
    assert f'"entity_id": {vendor.id}' in response.text
    assert "Vendor name is required." in response.text
