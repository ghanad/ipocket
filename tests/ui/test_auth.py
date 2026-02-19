from __future__ import annotations

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
    """Login page should preserve return_to parameter in the form."""
    response = client.get("/ui/login?return_to=/ui/audit-log")
    assert response.status_code == 200
    assert 'name="return_to"' in response.text
    assert 'value="/ui/audit-log"' in response.text


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
