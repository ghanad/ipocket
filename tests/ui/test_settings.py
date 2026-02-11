from __future__ import annotations

import re

from app import repository
from app.main import app
from app.models import UserRole
from app.routes import ui
from app.routes.ui import settings as settings_routes


def _override_editor(user) -> None:
    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    app.dependency_overrides[ui.get_current_ui_user] = lambda: user


def _clear_overrides() -> None:
    app.dependency_overrides.pop(ui.require_ui_editor, None)
    app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_projects_returns_404_for_missing_resources(client, _setup_connection) -> None:
    response_project = client.get("/ui/projects?edit=999")
    response_tag = client.get("/ui/projects?tab=tags&edit=999")
    response_vendor = client.get("/ui/projects?tab=vendors&delete=999")

    assert response_project.status_code == 404
    assert response_project.json()["detail"] == "Project not found"
    assert response_tag.status_code == 404
    assert response_tag.json()["detail"] == "Tag not found"
    assert response_vendor.status_code == 404
    assert response_vendor.json()["detail"] == "Vendor not found"


def test_create_project_validation_and_duplicate_errors(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        repository.create_project(connection, name="core")
    finally:
        connection.close()

    _override_editor(user)
    try:
        invalid_color = client.post(
            "/ui/projects",
            data={"name": "new-project", "description": "x", "color": "not-a-color"},
        )
        duplicate = client.post(
            "/ui/projects",
            data={"name": "core", "description": "x", "color": "#22c55e"},
        )
    finally:
        _clear_overrides()

    assert invalid_color.status_code == 400
    assert "Project color must be a valid hex color" in invalid_color.text
    assert duplicate.status_code == 409
    assert "Project name already exists." in duplicate.text


def test_update_project_handles_404_and_duplicate_name(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        first = repository.create_project(connection, name="first")
        repository.create_project(connection, name="second")
    finally:
        connection.close()

    _override_editor(user)
    try:
        missing_project = client.post(
            "/ui/projects/999/edit",
            data={"name": "", "description": "", "color": "#22c55e"},
        )
        duplicate = client.post(
            f"/ui/projects/{first.id}/edit",
            data={"name": "second", "description": "", "color": "#22c55e"},
        )
    finally:
        _clear_overrides()

    assert missing_project.status_code == 404
    assert duplicate.status_code == 409
    assert "Project name already exists." in duplicate.text


def test_tag_routes_redirect_and_validation_paths(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        tag = repository.create_tag(connection, name="prod")
    finally:
        connection.close()

    _override_editor(user)
    try:
        edit_redirect = client.get(f"/ui/tags/{tag.id}/edit", follow_redirects=False)
        delete_redirect = client.get(
            f"/ui/tags/{tag.id}/delete", follow_redirects=False
        )
        invalid_name = client.post(
            "/ui/tags",
            data={"name": "bad name", "color": "#22c55e"},
        )
        duplicate = client.post(
            "/ui/tags",
            data={"name": "prod", "color": "#22c55e"},
        )
        edit_missing_tag = client.post(
            "/ui/tags/999/edit",
            data={"name": "", "color": "#22c55e"},
        )
    finally:
        _clear_overrides()

    assert edit_redirect.status_code == 303
    assert edit_redirect.headers["location"].endswith(
        f"/ui/projects?tab=tags&edit={tag.id}"
    )
    assert delete_redirect.status_code == 303
    assert delete_redirect.headers["location"].endswith(
        f"/ui/projects?tab=tags&delete={tag.id}"
    )
    assert invalid_name.status_code == 400
    assert "Tag name may include letters, digits, dash, and underscore only." in invalid_name.text
    assert duplicate.status_code == 409
    assert "Tag name already exists." in duplicate.text
    assert edit_missing_tag.status_code == 404


def test_vendor_routes_cover_redirect_validation_and_delete_404(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        vendor = repository.create_vendor(connection, name="Cisco")
        repository.create_vendor(connection, name="Arista")
    finally:
        connection.close()

    _override_editor(user)
    try:
        edit_redirect = client.get(
            f"/ui/vendors/{vendor.id}/edit", follow_redirects=False
        )
        delete_redirect = client.get(
            f"/ui/vendors/{vendor.id}/delete", follow_redirects=False
        )
        create_empty = client.post("/ui/vendors", data={"name": ""})
        create_duplicate = client.post("/ui/vendors", data={"name": "Cisco"})
        edit_duplicate = client.post(
            f"/ui/vendors/{vendor.id}/edit",
            data={"name": "Arista"},
        )
        edit_missing = client.post("/ui/vendors/999/edit", data={"name": ""})
        delete_missing = client.post(
            "/ui/vendors/999/delete", data={"confirm_name": "whatever"}
        )
    finally:
        _clear_overrides()

    assert edit_redirect.status_code == 303
    assert edit_redirect.headers["location"].endswith(
        f"/ui/projects?tab=vendors&edit={vendor.id}"
    )
    assert delete_redirect.status_code == 303
    assert delete_redirect.headers["location"].endswith(
        f"/ui/projects?tab=vendors&delete={vendor.id}"
    )
    assert create_empty.status_code == 400
    assert "Vendor name is required." in create_empty.text
    assert create_duplicate.status_code == 409
    assert "Vendor name already exists." in create_duplicate.text
    assert edit_duplicate.status_code == 409
    assert "Vendor name already exists." in edit_duplicate.text
    assert edit_missing.status_code == 404
    assert delete_missing.status_code == 404


def test_audit_log_pagination_defaults_and_system_user_label(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="viewer",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
        for idx in range(12):
            repository.create_audit_log(
                connection,
                user=None,
                action="UPDATED",
                target_type="IP_ASSET",
                target_id=idx + 1,
                target_label=f"10.0.0.{idx + 1}",
            )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.get("/ui/audit-log?per-page=15&page=999")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert re.search(r"Showing\s+1-12\s+of\s+12", response.text)
    assert re.search(r'<option value="20"\s+selected>', response.text)
    assert "System" in response.text


def test_create_project_success_and_delete_guard_paths(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor-create-project",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    _override_editor(user)
    try:
        created = client.post(
            "/ui/projects",
            data={"name": "platform", "description": "", "color": ""},
            follow_redirects=False,
        )
        assert created.status_code == 303

        connection = _setup_connection()
        try:
            project = next(p for p in repository.list_projects(connection) if p.name == "platform")
        finally:
            connection.close()

        mismatch = client.post(
            f"/ui/projects/{project.id}/delete",
            data={"confirm_name": "wrong"},
        )
        assert mismatch.status_code == 400
        assert "Project name confirmation does not match." in mismatch.text

        monkeypatch.setattr(settings_routes.repository, "delete_project", lambda *_: False)
        blocked = client.post(
            f"/ui/projects/{project.id}/delete",
            data={"confirm_name": "platform"},
        )
    finally:
        _clear_overrides()

    assert blocked.status_code == 404


def test_tags_listing_and_edit_delete_branches(client, _setup_connection, monkeypatch) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor-tags-branches",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        primary = repository.create_tag(connection, name="prod")
        repository.create_tag(connection, name="edge")
    finally:
        connection.close()

    assert client.get("/ui/tags?edit=999").status_code == 404
    assert client.get("/ui/tags?delete=999").status_code == 404

    _override_editor(user)
    try:
        bad_color = client.post(
            f"/ui/tags/{primary.id}/edit",
            data={"name": "prod", "color": "nope"},
        )
        duplicate = client.post(
            f"/ui/tags/{primary.id}/edit",
            data={"name": "edge", "color": "#22c55e"},
        )
        monkeypatch.setattr(settings_routes.repository, "update_tag", lambda *_: None)
        missing_after_update = client.post(
            f"/ui/tags/{primary.id}/edit",
            data={"name": "prod-x", "color": "#22c55e"},
        )
        monkeypatch.setattr(settings_routes.repository, "delete_tag", lambda *_: False)
        delete_blocked = client.post(
            f"/ui/tags/{primary.id}/delete",
            data={"confirm_name": "prod"},
        )
    finally:
        _clear_overrides()

    assert bad_color.status_code == 400
    assert "Tag color must be a valid hex color" in bad_color.text
    assert duplicate.status_code == 409
    assert "Tag name already exists." in duplicate.text
    assert missing_after_update.status_code == 404
    assert delete_blocked.status_code == 404


def test_vendor_listing_create_edit_delete_branches(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor-vendor-branches",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        vendor = repository.create_vendor(connection, name="Cisco")
    finally:
        connection.close()

    assert client.get("/ui/vendors?edit=999").status_code == 404
    assert client.get("/ui/vendors?delete=999").status_code == 404

    _override_editor(user)
    try:
        created = client.post(
            "/ui/vendors",
            data={"name": "Juniper"},
            follow_redirects=False,
        )
        assert created.status_code == 303

        monkeypatch.setattr(settings_routes.repository, "update_vendor", lambda *_: None)
        update_missing = client.post(
            f"/ui/vendors/{vendor.id}/edit",
            data={"name": "Cisco-updated"},
        )
        delete_mismatch = client.post(
            f"/ui/vendors/{vendor.id}/delete",
            data={"confirm_name": "wrong"},
        )
        monkeypatch.setattr(settings_routes.repository, "delete_vendor", lambda *_: False)
        delete_blocked = client.post(
            f"/ui/vendors/{vendor.id}/delete",
            data={"confirm_name": "Cisco"},
        )
    finally:
        _clear_overrides()

    assert update_missing.status_code == 404
    assert delete_mismatch.status_code == 400
    assert "Vendor name confirmation does not match." in delete_mismatch.text
    assert delete_blocked.status_code == 404
