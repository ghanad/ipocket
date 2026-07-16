from __future__ import annotations

from app import repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def _editor() -> User:
    return User(1, "editor", "x", UserRole.EDITOR, True)


def test_ui_ranges_api_lists_utilization(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        ip_range = repository.create_ip_range(
            connection,
            name="Corp LAN",
            cidr="192.168.10.0/24",
            notes="office",
        )
        repository.create_ip_asset(
            connection,
            ip_address="192.168.10.10",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    response = client.get("/api/ui/ranges")

    assert response.status_code == 200
    assert response.json() == {
        "ranges": [
            {
                "id": ip_range.id,
                "name": "Corp LAN",
                "cidr": "192.168.10.0/24",
                "notes": "office",
                "total_usable": 254,
                "used": 1,
                "free": 253,
                "utilization_percent": 1 / 254 * 100,
            }
        ]
    }


def test_ui_ranges_api_create_update_delete_flow(client) -> None:
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        created = client.post(
            "/api/ui/ranges",
            json={
                "name": "  Corp LAN  ",
                "cidr": "192.168.10.17/24",
                "notes": " office ",
            },
        )
        assert created.status_code == 201
        assert created.json()["name"] == "Corp LAN"
        assert created.json()["cidr"] == "192.168.10.0/24"
        assert created.json()["notes"] == "office"
        range_id = created.json()["id"]

        updated = client.patch(
            f"/api/ui/ranges/{range_id}",
            json={
                "name": "Corporate LAN",
                "cidr": "192.168.20.10/24",
                "notes": "",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["cidr"] == "192.168.20.0/24"
        assert updated.json()["notes"] is None

        wrong_confirmation = client.request(
            "DELETE",
            f"/api/ui/ranges/{range_id}",
            json={"confirm_name": "Wrong"},
        )
        assert wrong_confirmation.status_code == 400
        assert "نام رنج" in wrong_confirmation.json()["detail"]

        deleted = client.request(
            "DELETE",
            f"/api/ui/ranges/{range_id}",
            json={"confirm_name": "Corporate LAN"},
        )
        assert deleted.status_code == 204
        assert client.get("/api/ui/ranges").json() == {"ranges": []}
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)


def test_ui_ranges_api_reports_validation_conflicts_and_missing_rows(
    client,
) -> None:
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        missing_name = client.post(
            "/api/ui/ranges",
            json={"name": " ", "cidr": "", "notes": ""},
        )
        assert missing_name.status_code == 422
        messages = [item["msg"] for item in missing_name.json()["detail"]]
        assert any("Range name is required." in message for message in messages)
        assert any("CIDR is required." in message for message in messages)

        first = client.post(
            "/api/ui/ranges",
            json={"name": "First", "cidr": "10.20.0.0/24"},
        )
        assert first.status_code == 201
        duplicate = client.post(
            "/api/ui/ranges",
            json={"name": "Duplicate", "cidr": "10.20.0.10/24"},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "CIDR already exists."

        missing_update = client.patch(
            "/api/ui/ranges/999",
            json={"name": "Missing", "cidr": "10.30.0.0/24"},
        )
        assert missing_update.status_code == 404
        missing_delete = client.request(
            "DELETE",
            "/api/ui/ranges/999",
            json={"confirm_name": "Missing"},
        )
        assert missing_delete.status_code == 404
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)


def test_ui_ranges_api_uses_the_existing_ui_session_cookie(
    client,
    _create_user,
) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    login = client.post(
        "/ui/login",
        data={
            "username": "editor",
            "password": "editor-pass",
            "return_to": "/ui/ranges",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303

    created = client.post(
        "/api/ui/ranges",
        json={"name": "Session Range", "cidr": "10.90.0.0/24"},
    )

    assert created.status_code == 201
    assert created.json()["name"] == "Session Range"


def test_ui_ranges_api_rejects_viewer_writes(client, _create_user) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    login = client.post(
        "/ui/login",
        data={
            "username": "viewer",
            "password": "viewer-pass",
            "return_to": "/ui/ranges",
        },
        follow_redirects=False,
    )
    assert login.status_code == 303

    response = client.post(
        "/api/ui/ranges",
        json={"name": "Forbidden", "cidr": "10.91.0.0/24"},
    )

    assert response.status_code == 403
