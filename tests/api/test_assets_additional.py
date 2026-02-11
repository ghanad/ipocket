from __future__ import annotations

from app.models import UserRole


def _editor_headers(_create_user, _login, _auth_headers) -> dict[str, str]:
    _create_user("editor-assets-extra", "editor-pass", UserRole.EDITOR)
    return _auth_headers(_login("editor-assets-extra", "editor-pass"))


def test_create_ip_asset_rejects_unknown_host_and_duplicate(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)

    unknown_host = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.200.0.10", "type": "VM", "host_id": 9999},
    )
    assert unknown_host.status_code == 422
    assert unknown_host.json()["detail"] == "Host not found."

    first = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.200.0.11", "type": "VM"},
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.200.0.11", "type": "VM"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "IP address already exists."


def test_list_and_get_ip_assets_include_tags_and_filters(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)

    project = client.post("/projects", headers=headers, json={"name": "Core"}).json()
    create = client.post(
        "/ip-assets",
        headers=headers,
        json={
            "ip_address": "10.201.0.10",
            "type": "VM",
            "project_id": project["id"],
            "tags": ["prod", "edge"],
        },
    )
    assert create.status_code == 200

    listed = client.get("/ip-assets", headers=headers, params={"type": "VM"})
    assert listed.status_code == 200
    assert any(asset["ip_address"] == "10.201.0.10" for asset in listed.json())

    listed_unassigned = client.get(
        "/ip-assets", headers=headers, params={"unassigned-only": "true"}
    )
    assert listed_unassigned.status_code == 200
    assert all(asset["project_id"] is None for asset in listed_unassigned.json())

    fetched = client.get("/ip-assets/10.201.0.10", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["ip_address"] == "10.201.0.10"
    assert fetched.json()["tags"] == ["edge", "prod"]



def test_update_ip_asset_rejects_unknown_host_and_missing_asset(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)

    client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.202.0.10", "type": "VM"},
    )

    unknown_host = client.patch(
        "/ip-assets/10.202.0.10",
        headers=headers,
        json={"host_id": 9999},
    )
    assert unknown_host.status_code == 422
    assert unknown_host.json()["detail"] == "Host not found."

    missing_asset = client.patch(
        "/ip-assets/10.202.0.99",
        headers=headers,
        json={"notes": "x"},
    )
    assert missing_asset.status_code == 404


def test_archive_ip_asset_success_and_not_found(
    client, _create_user, _login, _auth_headers
) -> None:
    headers = _editor_headers(_create_user, _login, _auth_headers)

    created = client.post(
        "/ip-assets",
        headers=headers,
        json={"ip_address": "10.203.0.10", "type": "VM"},
    )
    assert created.status_code == 200

    archived = client.post("/ip-assets/10.203.0.10/archive", headers=headers)
    assert archived.status_code == 204

    get_archived = client.get("/ip-assets/10.203.0.10", headers=headers)
    assert get_archived.status_code == 404

    missing = client.post("/ip-assets/10.203.0.99/archive", headers=headers)
    assert missing.status_code == 404
