from __future__ import annotations

from fastapi.testclient import TestClient as FastAPITestClient

from app import auth, repository
from app.main import app
from app.models import IPAssetType, UserRole


def test_login_happy_path(client, _create_user) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)

    response = client.post(
        "/login", json={"username": "viewer", "password": "viewer-pass"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_password_hashing_uses_bcrypt() -> None:
    hashed = auth.hash_password("sample-pass")
    assert hashed.startswith("$2")
    assert auth.verify_password("sample-pass", hashed)
    assert not auth.verify_password("wrong-pass", hashed)


def test_login_upgrades_legacy_sha256_hash(client, _setup_connection) -> None:
    legacy_hash = "c4ebc632c03529cf9f121d07055ee260606f7907540be42424cd2af15a0bf342"

    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection,
            username="legacy-user",
            hashed_password=legacy_hash,
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    response = client.post(
        "/login",
        json={"username": "legacy-user", "password": "legacy-pass"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]

    connection = _setup_connection()
    try:
        updated_user = repository.get_user_by_id(connection, user.id)
        assert updated_user is not None
        assert updated_user.hashed_password.startswith("$2")
    finally:
        connection.close()


def test_api_token_survives_app_restart(db_path, _create_user) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)

    with FastAPITestClient(app) as first_client:
        login_response = first_client.post(
            "/login", json={"username": "editor", "password": "editor-pass"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

    with FastAPITestClient(app) as second_client:
        create_response = second_client.post(
            "/ip-assets",
            headers={"Authorization": f"Bearer {token}"},
            json={"ip_address": "10.0.2.2", "type": IPAssetType.VM.value},
        )
        assert create_response.status_code == 200


def test_clear_tokens_revokes_api_sessions(client, _create_user, _login, _auth_headers):
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    token = _login("editor", "editor-pass")

    auth.clear_tokens()

    response = client.post(
        "/ip-assets",
        headers=_auth_headers(token),
        json={"ip_address": "10.0.2.3", "type": IPAssetType.VM.value},
    )
    assert response.status_code == 401


def test_auth_required_for_write_endpoints(client) -> None:
    response = client.post(
        "/ip-assets",
        json={
            "ip_address": "10.0.0.30",
            "type": IPAssetType.VM.value,
        },
    )

    assert response.status_code == 401


def test_viewer_cannot_write(
    client, db_path, _create_user, _login, _auth_headers, _setup_connection
) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    connection = _setup_connection()
    try:
        from app import repository

        repository.create_ip_asset(
            connection, ip_address="10.0.0.33", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    token = _login("viewer", "viewer-pass")
    headers = _auth_headers(token)

    response = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.0.0.31", "type": IPAssetType.VM.value},
    )
    assert response.status_code == 403

    assert (
        client.patch(
            "/ip-assets/10.0.0.33", headers=headers, json={"notes": "blocked"}
        ).status_code
        == 403
    )
    assert (
        client.post("/ip-assets/10.0.0.33/archive", headers=headers).status_code == 403
    )
    assert (
        client.request("DELETE", "/ip-assets/10.0.0.33", headers=headers).status_code
        == 403
    )


def test_editor_can_create_update_and_delete(
    client, _create_user, _login, _auth_headers
) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    create_response = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.0.0.32", "type": IPAssetType.VM.value},
    )
    assert create_response.status_code == 200

    update_response = client.patch(
        "/ip-assets/10.0.0.32",
        headers=headers,
        json={"notes": "Updated", "type": IPAssetType.VIP.value},
    )
    assert update_response.status_code == 200
    assert update_response.json()["notes"] == "Updated"

    assert (
        client.request("DELETE", "/ip-assets/10.0.0.32", headers=headers).status_code
        == 204
    )


def test_range_create_permissions(client, _create_user, _login, _auth_headers) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    _create_user("editor", "editor-pass", UserRole.EDITOR)

    viewer_token = _login("viewer", "viewer-pass")
    response = client.post(
        "/ranges",
        headers=_auth_headers(viewer_token),
        json={"name": "Corp", "cidr": "192.168.10.0/24"},
    )
    assert response.status_code == 403

    editor_token = _login("editor", "editor-pass")
    editor_response = client.post(
        "/ranges",
        headers=_auth_headers(editor_token),
        json={"name": "Corp", "cidr": "192.168.10.0/24"},
    )
    assert editor_response.status_code == 200


def test_superuser_cannot_write_data_endpoints(
    client, _create_user, _login, _auth_headers
) -> None:
    _create_user("root", "root-pass", UserRole.SUPERUSER)
    headers = _auth_headers(_login("root", "root-pass"))

    response = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.0.1.10", "type": IPAssetType.VM.value},
    )

    assert response.status_code == 403
