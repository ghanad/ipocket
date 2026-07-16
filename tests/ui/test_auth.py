from __future__ import annotations

import hashlib
from http.cookies import SimpleCookie

from app import auth, db, repository
from app.models import IPAssetType, UserRole
from app.routes import ui
from app.routes.ui import utils as ui_utils


def test_logout_button_hidden_when_not_authenticated(client) -> None:
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "sidebar-account-actions" not in response.text
    assert "sidebar-logout-button" not in response.text
    assert "sidebar-password-link" not in response.text
    assert "sidebar-login-link" in response.text
    assert "ipocket dev (" in response.text


def test_layout_does_not_render_static_top_header(client) -> None:
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "IP Asset Management" not in response.text
    assert 'class="topbar"' not in response.text


def test_logout_button_shown_when_authenticated(client, monkeypatch) -> None:
    monkeypatch.setattr(ui, "_is_authenticated_request", lambda request: True)
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert "sidebar-account-actions" in response.text
    assert "sidebar-logout-button" in response.text
    assert "sidebar-account-danger" in response.text
    assert "sidebar-password-link" in response.text
    assert "sidebar-login-link" not in response.text


def test_audit_log_page_requires_authentication(client) -> None:
    """Unauthenticated users should be redirected to login page with return URL."""
    response = client.get("/ui/audit-log", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/ui/audit-log"


def test_ip_asset_detail_page_requires_authentication(client) -> None:
    """Unauthenticated users should be redirected to login page for IP asset detail."""
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        asset = repository.create_ip_asset(
            connection, ip_address="10.50.0.99", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ip-assets/{asset.id}", follow_redirects=False)
    assert response.status_code == 303
    assert (
        response.headers["Location"] == f"/ui/login?return_to=/ui/ip-assets/{asset.id}"
    )


def test_login_preserves_return_url(client) -> None:
    """Login page should bootstrap return_to for the React entry."""
    response = client.get("/ui/login?return_to=/ui/audit-log")

    assert response.status_code == 200
    assert 'id="login-root"' in response.text
    assert 'data-endpoint="/api/ui/login"' in response.text
    assert '"return_to": "/ui/audit-log"' in response.text
    assert 'src="/static/react/login/login.js"' in response.text


def test_login_page_is_a_lightweight_react_mount_without_navigation(client) -> None:
    response = client.get("/ui/login")

    assert response.status_code == 200
    assert response.text.count('id="login-root"') == 1
    assert 'id="login-bootstrap"' in response.text
    assert 'class="sidebar"' not in response.text
    assert "sidebar-login-link" not in response.text
    assert 'method="post" action="/ui/login"' not in response.text


def test_authenticated_user_can_open_login_without_revoking_existing_session(
    client, _create_user, _setup_connection
) -> None:
    _create_user("existing-user", "existing-pass", UserRole.VIEWER)
    login = client.post(
        "/api/ui/login",
        json={"username": "existing-user", "password": "existing-pass"},
    )
    signed_cookie = login.cookies.get(ui.SESSION_COOKIE)
    assert signed_cookie
    token = ui_utils._verify_session_value(signed_cookie)
    assert token

    page = client.get("/ui/login")

    assert page.status_code == 200
    assert 'id="login-root"' in page.text
    connection = _setup_connection()
    try:
        assert auth.get_user_id_for_token(connection, token) is not None
    finally:
        connection.close()


def test_json_login_defaults_to_ip_assets_and_trims_username(
    client, _create_user
) -> None:
    _create_user("trimmed-user", "login-pass", UserRole.VIEWER)

    response = client.post(
        "/api/ui/login",
        json={"username": "  trimmed-user  ", "password": "login-pass"},
    )

    assert response.status_code == 200
    assert response.json() == {"redirect_to": "/ui/ip-assets"}


def test_json_login_preserves_server_approved_return_target(
    client, _create_user
) -> None:
    _create_user("return-user", "login-pass", UserRole.VIEWER)

    response = client.post(
        "/api/ui/login",
        json={
            "username": "return-user",
            "password": "login-pass",
            "return_to": "/ui/audit-log?scope=recent",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"redirect_to": "/ui/audit-log?scope=recent"}


def test_json_login_rejects_external_return_target(client, _create_user) -> None:
    _create_user("safe-return-user", "login-pass", UserRole.VIEWER)

    response = client.post(
        "/api/ui/login",
        json={
            "username": "safe-return-user",
            "password": "login-pass",
            "return_to": "//external.example/path",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"redirect_to": "/ui/ip-assets"}


def test_json_login_authentication_failures_are_identical(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        repository.create_user(
            connection,
            username="active-user",
            hashed_password=auth.hash_password("correct-pass"),
            role=UserRole.VIEWER,
        )
        repository.create_user(
            connection,
            username="inactive-user",
            hashed_password=auth.hash_password("correct-pass"),
            role=UserRole.VIEWER,
            is_active=False,
        )
    finally:
        connection.close()

    responses = [
        client.post(
            "/api/ui/login",
            json={"username": "missing-user", "password": "correct-pass"},
        ),
        client.post(
            "/api/ui/login",
            json={"username": "active-user", "password": "wrong-pass"},
        ),
        client.post(
            "/api/ui/login",
            json={"username": "inactive-user", "password": "correct-pass"},
        ),
    ]

    assert {response.status_code for response in responses} == {401}
    assert {response.text for response in responses} == {
        '{"detail":"Invalid username or password."}'
    }


def test_json_login_creates_database_session_and_secure_cookie_contract(
    client, _create_user, _setup_connection
) -> None:
    _create_user("json-session-user", "session-pass", UserRole.EDITOR)

    response = client.post(
        "/api/ui/login",
        json={"username": "json-session-user", "password": "session-pass"},
    )

    assert response.status_code == 200
    cookie_headers = response.headers.get_list("set-cookie")
    cookie_header = next(
        header
        for header in cookie_headers
        if header.startswith(f"{ui.SESSION_COOKIE}=")
    )
    jar = SimpleCookie()
    jar.load(cookie_header)
    session_cookie = jar[ui.SESSION_COOKIE]
    assert session_cookie["httponly"] is True
    assert session_cookie["samesite"].lower() == "lax"
    assert session_cookie["path"] == "/"
    assert not session_cookie["secure"]

    token = ui_utils._verify_session_value(session_cookie.value)
    assert token is not None
    connection = _setup_connection()
    try:
        user_id = auth.get_user_id_for_token(connection, token)
        user = repository.get_user_by_id(connection, user_id) if user_id else None
        assert user is not None
        assert user.username == "json-session-user"
    finally:
        connection.close()


def test_json_login_upgrades_valid_legacy_sha256_password(
    client, _setup_connection
) -> None:
    legacy_hash = hashlib.sha256(b"legacy-pass").hexdigest()
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="legacy-ui-user",
            hashed_password=legacy_hash,
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    response = client.post(
        "/api/ui/login",
        json={"username": "legacy-ui-user", "password": "legacy-pass"},
    )

    assert response.status_code == 200
    connection = _setup_connection()
    try:
        updated = repository.get_user_by_id(connection, user.id)
        assert updated is not None
        assert updated.hashed_password.startswith("$2")
    finally:
        connection.close()


def test_json_login_does_not_upgrade_invalid_legacy_password(
    client, _setup_connection
) -> None:
    legacy_hash = hashlib.sha256(b"legacy-pass").hexdigest()
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="invalid-legacy-ui-user",
            hashed_password=legacy_hash,
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    response = client.post(
        "/api/ui/login",
        json={"username": "invalid-legacy-ui-user", "password": "wrong-pass"},
    )

    assert response.status_code == 401
    connection = _setup_connection()
    try:
        unchanged = repository.get_user_by_id(connection, user.id)
        assert unchanged is not None
        assert unchanged.hashed_password == legacy_hash
    finally:
        connection.close()


def test_json_login_response_never_contains_credentials_or_session_secrets(
    client, _setup_connection
) -> None:
    password = "do-not-return-this-password"
    stored_hash = auth.hash_password(password)
    connection = _setup_connection()
    try:
        repository.create_user(
            connection,
            username="private-user",
            hashed_password=stored_hash,
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    response = client.post(
        "/api/ui/login",
        json={"username": "private-user", "password": password},
    )

    body = response.text
    signed_cookie = response.cookies.get(ui.SESSION_COOKIE)
    assert signed_cookie is not None
    token = ui_utils._verify_session_value(signed_cookie)
    assert token is not None
    assert response.status_code == 200
    assert password not in body
    assert stored_hash not in body
    assert signed_cookie not in body
    assert token not in body
    assert set(response.json()) == {"redirect_to"}


def test_json_login_rejects_invalid_json_and_field_types_without_echoing_input(
    client,
) -> None:
    invalid_json = client.post(
        "/api/ui/login",
        content='{"username": "user", "password": "secret"',
        headers={"Content-Type": "application/json"},
    )
    invalid_type = client.post(
        "/api/ui/login",
        json={"username": "user", "password": ["secret"]},
    )

    for response in (invalid_json, invalid_type):
        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid login request."}
        assert "secret" not in response.text


def test_login_redirects_to_return_url_after_success(client) -> None:
    """After successful login, user should be redirected to the return URL."""
    import os
    from app.auth import hash_password

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_user(
            connection, "testuser", hash_password("testpass"), UserRole.VIEWER
        )
    finally:
        connection.close()

    response = client.post(
        "/ui/login",
        data={
            "username": "testuser",
            "password": "testpass",
            "return_to": "/ui/audit-log",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/audit-log"


def test_legacy_login_failure_renders_react_shell_with_safe_bootstrap(
    client, _create_user
) -> None:
    _create_user("legacy-form-user", "correct-pass", UserRole.VIEWER)

    response = client.post(
        "/ui/login",
        data={
            "username": "legacy-form-user",
            "password": "wrong-pass",
            "return_to": "/ui/audit-log",
        },
    )

    assert response.status_code == 401
    assert 'id="login-root"' in response.text
    assert '"error_message": "Invalid username or password."' in response.text
    assert '"return_to": "/ui/audit-log"' in response.text
    assert '"username": "legacy-form-user"' in response.text
    assert "wrong-pass" not in response.text


def test_ui_login_creates_database_session_and_logout_revokes_it(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        repository.create_user(
            connection,
            username="session-user",
            hashed_password=auth.hash_password("session-pass"),
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    login_response = client.post(
        "/ui/login",
        data={"username": "session-user", "password": "session-pass"},
        follow_redirects=False,
    )
    assert login_response.status_code == 303

    cookie_header = login_response.headers.get("set-cookie")
    assert cookie_header is not None
    jar = SimpleCookie()
    jar.load(cookie_header)
    assert ui.SESSION_COOKIE in jar
    signed_cookie_value = jar[ui.SESSION_COOKIE].value
    session_token = ui_utils._verify_session_value(signed_cookie_value)
    assert session_token is not None

    connection = _setup_connection()
    try:
        assert auth.get_user_id_for_token(connection, session_token) is not None
    finally:
        connection.close()

    logout_response = client.post(
        "/ui/logout",
        headers={"Cookie": f"{ui.SESSION_COOKIE}={signed_cookie_value}"},
        follow_redirects=False,
    )
    assert logout_response.status_code == 303

    connection = _setup_connection()
    try:
        assert auth.get_user_id_for_token(connection, session_token) is None
    finally:
        connection.close()
