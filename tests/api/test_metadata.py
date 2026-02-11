from __future__ import annotations

from app.models import UserRole


def test_projects_crud_and_list_flow(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    created = client.post(
        "/projects",
        headers=headers,
        json={"name": "Core", "description": "Main", "color": "#ABCDEF"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["name"] == "Core"
    assert payload["description"] == "Main"
    assert payload["color"] == "#abcdef"

    listed = client.get("/projects", headers=headers)
    assert listed.status_code == 200
    assert any(project["name"] == "Core" for project in listed.json())

    updated = client.patch(
        f"/projects/{payload['id']}",
        headers=headers,
        json={"name": "Core-Updated", "description": "Updated", "color": "#123456"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Core-Updated"
    assert updated.json()["color"] == "#123456"

    missing = client.patch(
        "/projects/9999",
        headers=headers,
        json={"name": "x"},
    )
    assert missing.status_code == 404


def test_vendors_crud_and_list_flow(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    created = client.post("/vendors", headers=headers, json={"name": "  Dell  "})
    assert created.status_code == 200
    vendor_id = created.json()["id"]
    assert created.json()["name"] == "Dell"

    listed = client.get("/vendors", headers=headers)
    assert listed.status_code == 200
    assert any(vendor["name"] == "Dell" for vendor in listed.json())

    updated = client.patch(
        f"/vendors/{vendor_id}",
        headers=headers,
        json={"name": "  Lenovo  "},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Lenovo"

    missing = client.patch(
        "/vendors/9999",
        headers=headers,
        json={"name": "nope"},
    )
    assert missing.status_code == 404


def test_ranges_create_and_list_flow(client, _create_user, _login, _auth_headers) -> None:
    _create_user("editor", "editor-pass", UserRole.EDITOR)
    headers = _auth_headers(_login("editor", "editor-pass"))

    created = client.post(
        "/ranges",
        headers=headers,
        json={"name": "Corp LAN", "cidr": "192.168.10.17/24", "notes": "office"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["name"] == "Corp LAN"
    assert payload["cidr"] == "192.168.10.0/24"
    assert payload["notes"] == "office"
    assert payload["created_at"]
    assert payload["updated_at"]

    listed = client.get("/ranges", headers=headers)
    assert listed.status_code == 200
    assert any(ip_range["cidr"] == "192.168.10.0/24" for ip_range in listed.json())


def test_metadata_writes_require_editor_role(
    client, _create_user, _login, _auth_headers
) -> None:
    _create_user("viewer", "viewer-pass", UserRole.VIEWER)
    headers = _auth_headers(_login("viewer", "viewer-pass"))

    assert client.post("/projects", headers=headers, json={"name": "Core"}).status_code == 403
    assert client.post("/vendors", headers=headers, json={"name": "Dell"}).status_code == 403
    assert (
        client.post(
            "/ranges",
            headers=headers,
            json={"name": "Lab", "cidr": "10.10.0.0/24"},
        ).status_code
        == 403
    )
