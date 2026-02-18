from __future__ import annotations

from app import auth, repository
from app.main import app
from app.models import UserRole
from app.routes import ui


def test_account_password_page_requires_authentication(client) -> None:
    response = client.get("/ui/account/password", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/ui/account/password"


def test_change_password_happy_path_updates_credentials_and_writes_audit_log(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="viewer",
            hashed_password=auth.hash_password("viewer-pass"),
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.post(
            "/ui/account/password",
            data={
                "current_password": "viewer-pass",
                "new_password": "viewer-pass-2",
                "confirm_new_password": "viewer-pass-2",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/account/password"

    old_login = client.post(
        "/login",
        json={"username": "viewer", "password": "viewer-pass"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/login",
        json={"username": "viewer", "password": "viewer-pass-2"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]

    connection = _setup_connection()
    try:
        logs = repository.list_audit_logs(connection, target_type="USER", limit=10)
        assert len(logs) == 1
        assert logs[0].action == "UPDATE"
        assert logs[0].target_id == user.id
        assert logs[0].target_label == "viewer"
        assert logs[0].changes == "password: self-service rotated"
    finally:
        connection.close()


def test_change_password_rejects_incorrect_current_password(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="editor",
            hashed_password=auth.hash_password("editor-pass"),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.post(
            "/ui/account/password",
            data={
                "current_password": "wrong-pass",
                "new_password": "editor-pass-2",
                "confirm_new_password": "editor-pass-2",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Current password is incorrect." in response.text

    old_login = client.post(
        "/login",
        json={"username": "editor", "password": "editor-pass"},
    )
    assert old_login.status_code == 200


def test_change_password_rejects_mismatched_confirmation(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="mismatch-user",
            hashed_password=auth.hash_password("mismatch-pass"),
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.post(
            "/ui/account/password",
            data={
                "current_password": "mismatch-pass",
                "new_password": "next-pass",
                "confirm_new_password": "different-pass",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "New password and confirmation do not match." in response.text


def test_change_password_rejects_reusing_current_password(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="same-pass-user",
            hashed_password=auth.hash_password("same-pass"),
            role=UserRole.SUPERUSER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.post(
            "/ui/account/password",
            data={
                "current_password": "same-pass",
                "new_password": "same-pass",
                "confirm_new_password": "same-pass",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "New password must be different from current password." in response.text
