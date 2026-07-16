from __future__ import annotations

import pytest

from app import auth, repository
from app.main import app
from app.models import UserRole
from app.routes import ui


def _create_user(_setup_connection, *, username: str, password: str, role: UserRole):
    connection = _setup_connection()
    try:
        return repository.create_user(
            connection,
            username=username,
            hashed_password=auth.hash_password(password),
            role=role,
        )
    finally:
        connection.close()


def _post_json(client, user, payload: dict[str, str]):
    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        return client.post("/api/ui/account/password", json=payload)
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def _post_legacy(client, user, payload: dict[str, str]):
    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        return client.post(
            "/ui/account/password",
            data=payload,
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_account_password_page_and_api_require_authentication(client) -> None:
    page = client.get("/ui/account/password", follow_redirects=False)
    api = client.post(
        "/api/ui/account/password",
        json={
            "current_password": "old",
            "new_password": "new",
            "confirm_new_password": "new",
        },
        follow_redirects=False,
    )

    assert page.status_code == 303
    assert page.headers["Location"] == "/ui/login?return_to=/ui/account/password"
    assert api.status_code == 303
    assert (
        api.headers["Location"]
        == "/ui/login?return_to=/api/ui/account/password"
    )


def test_account_password_page_is_a_lightweight_react_mount(
    client, _setup_connection
) -> None:
    user = _create_user(
        _setup_connection,
        username="mount-user",
        password="mount-pass",
        role=UserRole.VIEWER,
    )
    app.dependency_overrides[ui.get_current_ui_user] = lambda: user
    try:
        response = client.get("/ui/account/password")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert 'id="account-password-root"' in response.text
    assert 'data-endpoint="/api/ui/account/password"' in response.text
    assert (
        'src="/static/react/account-password/account-password.js"'
        in response.text
    )
    assert 'style="max-width: 640px"' not in response.text
    assert 'name="current_password"' not in response.text
    assert '<form method="post" action="/ui/account/password"' not in response.text


@pytest.mark.parametrize(
    "role",
    [UserRole.VIEWER, UserRole.EDITOR, UserRole.SUPERUSER],
)
def test_every_authenticated_role_can_rotate_only_its_own_password(
    client, _setup_connection, role: UserRole
) -> None:
    username = f"{role.value.lower()}-self-service"
    old_password = f"{role.value.lower()}-old"
    new_password = f"{role.value.lower()}-new"
    user = _create_user(
        _setup_connection,
        username=username,
        password=old_password,
        role=role,
    )
    other_user = _create_user(
        _setup_connection,
        username=f"{username}-other",
        password="other-user-pass",
        role=UserRole.VIEWER,
    )

    response = _post_json(
        client,
        user,
        {
            "current_password": old_password,
            "new_password": new_password,
            "confirm_new_password": new_password,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully."}
    assert old_password not in response.text
    assert new_password not in response.text

    connection = _setup_connection()
    try:
        updated_user = repository.get_user_by_id(connection, user.id)
        unchanged_other = repository.get_user_by_id(connection, other_user.id)
        assert updated_user is not None
        assert unchanged_other is not None
        assert updated_user.hashed_password != user.hashed_password
        assert updated_user.hashed_password.startswith("$2")
        assert auth.verify_password(new_password, updated_user.hashed_password)
        assert unchanged_other.hashed_password == other_user.hashed_password
        assert updated_user.hashed_password not in response.text

        logs = repository.list_audit_logs(connection, target_type="USER", limit=10)
        assert len(logs) == 1
        assert logs[0].action == "UPDATE"
        assert logs[0].target_id == user.id
        assert logs[0].target_label == username
        assert logs[0].changes == "password: self-service rotated"
    finally:
        connection.close()

    old_login = client.post(
        "/login",
        json={"username": username, "password": old_password},
    )
    new_login = client.post(
        "/login",
        json={"username": username, "password": new_password},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {
                "current_password": "",
                "new_password": "next-pass",
                "confirm_new_password": "next-pass",
            },
            "Current password is required.",
        ),
        (
            {
                "current_password": "validation-pass",
                "new_password": "",
                "confirm_new_password": "confirmation",
            },
            "New password is required.",
        ),
        (
            {
                "current_password": "validation-pass",
                "new_password": "next-pass",
                "confirm_new_password": "",
            },
            "Confirm new password is required.",
        ),
        (
            {
                "current_password": "validation-pass",
                "new_password": "next-pass",
                "confirm_new_password": "different-pass",
            },
            "New password and confirmation do not match.",
        ),
        (
            {
                "current_password": "validation-pass",
                "new_password": "validation-pass",
                "confirm_new_password": "validation-pass",
            },
            "New password must be different from current password.",
        ),
        (
            {
                "current_password": "wrong-pass",
                "new_password": "next-pass",
                "confirm_new_password": "next-pass",
            },
            "Current password is incorrect.",
        ),
    ],
)
def test_json_password_validation_preserves_messages_and_does_not_audit(
    client,
    _setup_connection,
    payload: dict[str, str],
    expected_message: str,
) -> None:
    user = _create_user(
        _setup_connection,
        username="validation-user",
        password="validation-pass",
        role=UserRole.EDITOR,
    )

    response = _post_json(client, user, payload)

    assert response.status_code == 400
    assert expected_message in response.json()["detail"]
    for submitted_password in payload.values():
        if submitted_password:
            assert submitted_password not in response.text
    assert user.hashed_password not in response.text

    connection = _setup_connection()
    try:
        unchanged = repository.get_user_by_id(connection, user.id)
        assert unchanged is not None
        assert unchanged.hashed_password == user.hashed_password
        assert repository.list_audit_logs(
            connection, target_type="USER", limit=10
        ) == []
    finally:
        connection.close()


def test_json_password_validation_returns_all_required_messages(
    client, _setup_connection
) -> None:
    user = _create_user(
        _setup_connection,
        username="required-user",
        password="required-pass",
        role=UserRole.VIEWER,
    )

    response = _post_json(
        client,
        user,
        {
            "current_password": "",
            "new_password": "",
            "confirm_new_password": "",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == [
        "Current password is required.",
        "New password is required.",
        "Confirm new password is required.",
    ]


def test_missing_authenticated_user_is_handled_without_password_data(
    client,
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: None
    try:
        api_response = client.post(
            "/api/ui/account/password",
            json={
                "current_password": "missing-current",
                "new_password": "missing-new",
                "confirm_new_password": "missing-new",
            },
        )
        legacy_response = client.post(
            "/ui/account/password",
            data={
                "current_password": "missing-current",
                "new_password": "missing-new",
                "confirm_new_password": "missing-new",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert api_response.status_code == 404
    assert api_response.json() == {"detail": "Authenticated user not found."}
    assert "missing-current" not in api_response.text
    assert "missing-new" not in api_response.text
    assert legacy_response.status_code == 404


def test_legacy_form_route_uses_shared_validation_and_keeps_passwords_empty(
    client, _setup_connection
) -> None:
    user = _create_user(
        _setup_connection,
        username="legacy-validation",
        password="legacy-pass",
        role=UserRole.VIEWER,
    )

    response = _post_legacy(
        client,
        user,
        {
            "current_password": "wrong-pass",
            "new_password": "legacy-next",
            "confirm_new_password": "legacy-next",
        },
    )

    assert response.status_code == 400
    assert "Current password is incorrect." in response.text
    assert 'id="account-password-root"' in response.text
    assert "wrong-pass" not in response.text
    assert "legacy-next" not in response.text


def test_legacy_form_route_remains_compatible_for_success(
    client, _setup_connection
) -> None:
    user = _create_user(
        _setup_connection,
        username="legacy-success",
        password="legacy-old",
        role=UserRole.SUPERUSER,
    )

    response = _post_legacy(
        client,
        user,
        {
            "current_password": "legacy-old",
            "new_password": "legacy-new",
            "confirm_new_password": "legacy-new",
        },
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/account/password"

    connection = _setup_connection()
    try:
        updated = repository.get_user_by_id(connection, user.id)
        assert updated is not None
        assert auth.verify_password("legacy-new", updated.hashed_password)
        logs = repository.list_audit_logs(connection, target_type="USER", limit=10)
        assert len(logs) == 1
        assert logs[0].changes == "password: self-service rotated"
    finally:
        connection.close()
