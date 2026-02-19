from __future__ import annotations

from app import auth, repository
from app.main import app
from app.models import UserRole
from app.routes import ui


def test_users_page_requires_superuser_and_redirects_when_unauthenticated(
    client,
) -> None:
    response = client.get("/ui/users", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/ui/users"


def test_users_page_forbids_editor(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection,
            username="editor",
            hashed_password=auth.hash_password("editor-pass"),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: editor
    try:
        response = client.get("/ui/users")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403


def test_superuser_can_manage_users_from_ui(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        superuser = repository.create_user(
            connection,
            username="admin",
            hashed_password=auth.hash_password("admin-pass"),
            role=UserRole.SUPERUSER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        create_response = client.post(
            "/ui/users",
            data={
                "username": "operator",
                "password": "operator-pass",
                "can_edit": "1",
                "is_active": "1",
            },
            follow_redirects=False,
        )
        assert create_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    connection = _setup_connection()
    try:
        operator = repository.get_user_by_username(connection, "operator")
        assert operator is not None
        assert operator.role == UserRole.EDITOR
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        edit_response = client.post(
            f"/ui/users/{operator.id}/edit",
            data={
                "can_edit": "0",
                "password": "",
            },
            follow_redirects=False,
        )
        assert edit_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    connection = _setup_connection()
    try:
        updated = repository.get_user_by_username(connection, "operator")
        assert updated is not None
        assert updated.role == UserRole.VIEWER
        assert updated.is_active is False

        logs = repository.list_audit_logs(connection, target_type="USER", limit=10)
        assert len(logs) == 2
        assert [entry.action for entry in logs] == ["UPDATE", "CREATE"]
    finally:
        connection.close()


def test_sidebar_users_link_visible_only_to_superuser(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        superuser = repository.create_user(
            connection,
            username="admin",
            hashed_password=auth.hash_password("admin-pass"),
            role=UserRole.SUPERUSER,
        )
        editor = repository.create_user(
            connection,
            username="editor",
            hashed_password=auth.hash_password("editor-pass"),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    connection = _setup_connection()
    try:
        superuser_token = auth.create_access_token(connection, superuser.id)
        editor_token = auth.create_access_token(connection, editor.id)
    finally:
        connection.close()

    superuser_cookie = ui._sign_session_value(superuser_token)
    superuser_page = client.get(
        "/ui/management",
        headers={"Cookie": f"{ui.SESSION_COOKIE}={superuser_cookie}"},
    )
    assert superuser_page.status_code == 200
    assert 'href="/ui/users"' in superuser_page.text

    editor_cookie = ui._sign_session_value(editor_token)
    editor_page = client.get(
        "/ui/management",
        headers={"Cookie": f"{ui.SESSION_COOKIE}={editor_cookie}"},
    )
    assert editor_page.status_code == 200
    assert 'href="/ui/users"' not in editor_page.text


def test_users_page_renders_create_and_edit_drawers(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        superuser = repository.create_user(
            connection,
            username="admin",
            hashed_password=auth.hash_password("admin-pass"),
            role=UserRole.SUPERUSER,
        )
        repository.create_user(
            connection,
            username="operator",
            hashed_password=auth.hash_password("operator-pass"),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.get("/ui/users")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "data-user-create-drawer" in response.text
    assert "data-user-edit-drawer" in response.text
    assert "data-user-delete-drawer" in response.text
    assert "data-user-add" in response.text
    assert 'data-user-edit="' in response.text
    assert 'data-user-delete="' in response.text


def test_superuser_can_delete_user_and_keep_user_audit_logs(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        superuser = repository.create_user(
            connection,
            username="admin",
            hashed_password=auth.hash_password("admin-pass"),
            role=UserRole.SUPERUSER,
        )
        target = repository.create_user(
            connection,
            username="delete-me",
            hashed_password=auth.hash_password("x"),
            role=UserRole.VIEWER,
        )
        repository.create_audit_log(
            connection,
            user=target,
            action="CREATE",
            target_type="IP_ASSET",
            target_id=1,
            target_label="10.0.0.1",
            changes="created by target user",
        )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.post(
            f"/ui/users/{target.id}/delete",
            data={"confirm_username": "delete-me"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 303

    connection = _setup_connection()
    try:
        deleted = repository.get_user_by_id(connection, target.id)
        assert deleted is None
        asset_logs = repository.list_audit_logs(
            connection, target_type="IP_ASSET", limit=20
        )
        user_logs = repository.list_audit_logs(connection, target_type="USER", limit=20)
        assert any(log.user_id is None for log in asset_logs)
        assert any(
            log.action == "DELETE" and log.target_label == "delete-me"
            for log in user_logs
        )
    finally:
        connection.close()


def test_superuser_cannot_delete_own_account(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        superuser = repository.create_user(
            connection,
            username="admin",
            hashed_password=auth.hash_password("admin-pass"),
            role=UserRole.SUPERUSER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.post(
            f"/ui/users/{superuser.id}/delete",
            data={"confirm_username": "admin"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "You cannot delete your own account." in response.text
