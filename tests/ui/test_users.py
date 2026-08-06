from __future__ import annotations

import pytest

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


def test_users_api_redirects_when_unauthenticated(client) -> None:
    response = client.get("/api/ui/users", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/api/ui/users"


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.EDITOR])
def test_users_page_forbids_viewer_and_editor(client, _setup_connection, role) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username=role.value.lower(),
            hashed_password=auth.hash_password("user-pass"),
            role=role,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
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
    assert 'id="users-root"' in response.text
    assert 'data-endpoint="/api/ui/users"' in response.text
    assert (
        '<script type="module" src="/static/react/users/users.js"></script>'
        in response.text
    )
    assert "data-user-create-drawer" not in response.text
    assert "operator" not in response.text
    assert "/static/js/users.js" not in response.text


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


@pytest.mark.parametrize("role", [UserRole.VIEWER, UserRole.EDITOR])
def test_viewer_and_editor_cannot_access_user_management_api(
    client, _setup_connection, role
) -> None:
    connection = _setup_connection()
    try:
        actor = repository.create_user(
            connection,
            username=role.value.lower(),
            hashed_password=auth.hash_password("pass"),
            role=role,
        )
        target = repository.create_user(
            connection,
            username=f"{role.value.lower()}-target",
            hashed_password=auth.hash_password("pass"),
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    try:
        responses = [
            client.get("/api/ui/users"),
            client.post(
                "/api/ui/users",
                json={
                    "username": "blocked",
                    "password": "secret",
                    "can_edit": False,
                    "is_active": True,
                },
            ),
            client.patch(
                f"/api/ui/users/{target.id}",
                json={"can_edit": True, "is_active": True, "password": ""},
            ),
            client.request(
                "DELETE",
                f"/api/ui/users/{target.id}",
                json={"confirm_username": target.username},
            ),
        ]
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert [response.status_code for response in responses] == [403, 403, 403, 403]


def test_user_api_lists_safe_payload_and_actor_policy(
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
        repository.create_user(
            connection,
            username="viewer",
            hashed_password=auth.hash_password("viewer-pass"),
            role=UserRole.VIEWER,
            is_active=False,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.get("/api/ui/users")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["actor"] == {
        "id": superuser.id,
        "username": "admin",
        "role": "Admin",
    }
    assert [user["username"] for user in payload["users"]] == ["admin", "viewer"]
    assert payload["users"][0]["role_label"] == "Superuser"
    assert payload["users"][0]["policy"]["can_delete"] is False
    assert payload["users"][1]["is_active"] is False
    serialized = response.text.lower()
    assert "hashed_password" not in serialized
    assert "admin-pass" not in serialized
    assert "viewer-pass" not in serialized


@pytest.mark.parametrize(
    ("can_edit", "expected_role"),
    [(False, UserRole.VIEWER), (True, UserRole.EDITOR)],
)
def test_superuser_api_creates_user_with_hashed_password_and_role(
    client, _setup_connection, can_edit, expected_role
) -> None:
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

    username = f"new-{expected_role.value.lower()}"
    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.post(
            "/api/ui/users",
            json={
                "username": username,
                "password": "new-pass",
                "can_edit": can_edit,
                "is_active": False,
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 201
    assert "password" not in response.text.lower()

    connection = _setup_connection()
    try:
        created = repository.get_user_by_username(connection, username)
        assert created is not None
        assert created.role == expected_role
        assert created.is_active is False
        assert created.hashed_password != "new-pass"
        assert auth.verify_password("new-pass", created.hashed_password)
        logs = repository.list_audit_logs(connection, target_type="USER")
        assert logs[0].action == "CREATE"
        assert logs[0].target_label == username
        assert logs[0].changes == (
            f"Created user (role={expected_role.value}, is_active=0)"
        )
    finally:
        connection.close()


def test_user_api_rejects_duplicate_username_without_returning_password(
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
        repository.create_user(
            connection,
            username="duplicate",
            hashed_password=auth.hash_password("old-pass"),
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.post(
            "/api/ui/users",
            json={
                "username": "duplicate",
                "password": "plaintext-secret",
                "can_edit": True,
                "is_active": True,
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists."}
    assert "plaintext-secret" not in response.text


def test_user_api_validation_errors_never_echo_passwords(
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
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        missing_username = client.post(
            "/api/ui/users",
            json={
                "password": "never-reflect-this",
                "can_edit": False,
                "is_active": True,
            },
        )
        invalid_boolean = client.post(
            "/api/ui/users",
            json={
                "username": "new-user",
                "password": "also-never-reflect-this",
                "can_edit": "yes",
                "is_active": True,
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert missing_username.status_code == 422
    assert missing_username.json() == {"detail": "Username is required."}
    assert invalid_boolean.status_code == 422
    assert invalid_boolean.json() == {"detail": "Can edit must be true or false."}
    assert "never-reflect-this" not in missing_username.text
    assert "also-never-reflect-this" not in invalid_boolean.text


def test_user_api_updates_role_status_and_optional_password(
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
            username="operator",
            hashed_password=auth.hash_password("old-pass"),
            role=UserRole.VIEWER,
        )
        original_hash = target.hashed_password
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        first_response = client.patch(
            f"/api/ui/users/{target.id}",
            json={"can_edit": True, "is_active": False, "password": ""},
        )
        second_response = client.patch(
            f"/api/ui/users/{target.id}",
            json={
                "can_edit": True,
                "is_active": False,
                "password": "rotated-pass",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert first_response.status_code == 200
    assert first_response.json()["changed"] is True
    assert second_response.status_code == 200
    assert "password" not in second_response.text.lower()

    connection = _setup_connection()
    try:
        updated = repository.get_user_by_id(connection, target.id)
        assert updated is not None
        assert updated.role == UserRole.EDITOR
        assert updated.is_active is False
        assert updated.hashed_password != original_hash
        assert auth.verify_password("rotated-pass", updated.hashed_password)
        logs = repository.list_audit_logs(connection, target_type="USER")
        assert [log.action for log in logs] == ["UPDATE", "UPDATE"]
        assert logs[0].changes == "password: rotated"
        assert logs[1].changes == "role: Viewer -> Editor; is_active: 1 -> 0"
    finally:
        connection.close()


def test_user_api_noop_update_preserves_password_and_skips_audit(
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
            username="viewer",
            hashed_password=auth.hash_password("viewer-pass"),
            role=UserRole.VIEWER,
        )
        original_hash = target.hashed_password
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        response = client.patch(
            f"/api/ui/users/{target.id}",
            json={"can_edit": False, "is_active": True, "password": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert response.json()["changed"] is False

    connection = _setup_connection()
    try:
        unchanged = repository.get_user_by_id(connection, target.id)
        assert unchanged is not None
        assert unchanged.hashed_password == original_hash
        assert repository.list_audit_logs(connection, target_type="USER") == []
    finally:
        connection.close()


def test_user_api_protects_superuser_role_and_last_active_account(
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
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        role_response = client.patch(
            f"/api/ui/users/{superuser.id}",
            json={"can_edit": False, "is_active": True, "password": ""},
        )
        active_response = client.patch(
            f"/api/ui/users/{superuser.id}",
            json={"can_edit": True, "is_active": False, "password": ""},
        )
        delete_response = client.request(
            "DELETE",
            f"/api/ui/users/{superuser.id}",
            json={"confirm_username": "admin"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert role_response.status_code == 403
    assert role_response.json()["detail"] == "Superuser edit access cannot be changed."
    assert active_response.status_code == 403
    assert active_response.json()["detail"] == (
        "Cannot deactivate the last active superuser."
    )
    assert delete_response.status_code == 403
    assert delete_response.json()["detail"] == "You cannot delete your own account."


def test_user_api_requires_exact_delete_confirmation_and_preserves_audit_history(
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
            hashed_password=auth.hash_password("target-pass"),
            role=UserRole.EDITOR,
            is_active=False,
        )
        repository.create_audit_log(
            connection,
            user=target,
            action="UPDATE",
            target_type="IP_ASSET",
            target_id=99,
            target_label="10.0.0.99",
            changes="target history",
        )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        mismatch = client.request(
            "DELETE",
            f"/api/ui/users/{target.id}",
            json={"confirm_username": "Delete-Me"},
        )
        deleted = client.request(
            "DELETE",
            f"/api/ui/users/{target.id}",
            json={"confirm_username": "delete-me"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert mismatch.status_code == 422
    assert mismatch.json()["detail"] == "Username confirmation does not match."
    assert deleted.status_code == 204

    connection = _setup_connection()
    try:
        assert repository.get_user_by_id(connection, target.id) is None
        asset_logs = repository.list_audit_logs(
            connection, target_type="IP_ASSET", limit=10
        )
        assert asset_logs[0].user_id is None
        user_logs = repository.list_audit_logs(connection, target_type="USER", limit=10)
        assert user_logs[0].action == "DELETE"
        assert user_logs[0].target_label == "delete-me"
        assert user_logs[0].changes == ("Deleted user (role=Editor, is_active=0)")
    finally:
        connection.close()


def test_user_api_returns_404_for_missing_mutation_targets(
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
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: superuser
    try:
        update_response = client.patch(
            "/api/ui/users/9999",
            json={"can_edit": False, "is_active": True, "password": ""},
        )
        delete_response = client.request(
            "DELETE",
            "/api/ui/users/9999",
            json={"confirm_username": "missing"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    assert update_response.json() == {"detail": "User not found."}
    assert delete_response.json() == {"detail": "User not found."}


def test_user_api_prevents_deleting_last_active_superuser(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        inactive_actor = repository.create_user(
            connection,
            username="inactive-admin",
            hashed_password=auth.hash_password("actor-pass"),
            role=UserRole.SUPERUSER,
            is_active=False,
        )
        active_target = repository.create_user(
            connection,
            username="active-admin",
            hashed_password=auth.hash_password("target-pass"),
            role=UserRole.SUPERUSER,
            is_active=True,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: inactive_actor
    try:
        response = client.request(
            "DELETE",
            f"/api/ui/users/{active_target.id}",
            json={"confirm_username": "active-admin"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Cannot delete the last active superuser."}
