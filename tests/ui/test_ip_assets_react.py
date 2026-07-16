from __future__ import annotations

import os

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def _user(username: str, role: UserRole) -> User:
    return User(1, username, "x", role, True)


def test_ip_assets_react_shell_references_mount_and_generated_entry(client) -> None:
    response = client.get("/ui/ip-assets?q=10.0.0.1&per-page=50")

    assert response.status_code == 200
    assert 'id="ip-assets-root"' in response.text
    assert 'data-endpoint="/api/ui/ip-assets"' in response.text
    assert 'data-initial-query="q=10.0.0.1&amp;per-page=50"' in response.text
    assert "/static/react/ip-assets/ip-assets.js" in response.text
    assert "/static/js/ip-assets.js" not in response.text
    assert "hx-get=" not in response.text
    assert "ip-table-container" not in response.text


def test_ip_assets_list_api_normalizes_filters_and_bounds_pagination(client) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core", color="#2563eb")
        repository.create_tag(connection, name="prod", color="#22c55e")
        repository.create_tag(connection, name="edge", color="#0ea5e9")
        repository.create_tag(connection, name="deprecated", color="#ef4444")
        repository.create_ip_asset(
            connection,
            ip_address="10.1.0.1",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            tags=["prod", "edge"],
            notes="primary",
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.1.0.2",
            asset_type=IPAssetType.OS,
            tags=["prod", "deprecated"],
        )
    finally:
        connection.close()

    response = client.get(
        "/api/ui/ip-assets",
        params=[
            ("q", " 10.1 "),
            ("project_id", str(project.id)),
            ("type", "VM"),
            ("tag_all", "prod"),
            ("tag_any", "edge"),
            ("tag_not", "deprecated"),
            ("page", "999"),
            ("per-page", "999"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert [asset["ip_address"] for asset in payload["assets"]] == ["10.1.0.1"]
    assert payload["assets"][0]["delete_requires_exact_ip"] is True
    assert payload["assets"][0]["can_auto_host"] is False
    assert payload["filters"]["projects"] == [
        {"id": project.id, "name": "Core", "color": "#2563eb"}
    ]
    assert payload["filters"]["normalized"] == {
        "q": "10.1",
        "project_id": str(project.id),
        "type": "VM",
        "assigned_only": False,
        "unassigned_only": False,
        "archived_only": False,
        "tag_all": ["prod"],
        "tag_any": ["edge"],
        "tag_not": ["deprecated"],
        "page": 1,
        "per_page": 20,
    }
    assert payload["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 1,
        "total_pages": 1,
    }
    assert payload["can_edit"] is False


def test_ip_assets_list_api_supports_unassigned_archived_and_editor_policy(client) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        active = repository.create_ip_asset(
            connection,
            ip_address="10.2.0.1",
            asset_type=IPAssetType.OS,
        )
        assigned_active = repository.create_ip_asset(
            connection,
            ip_address="10.2.0.3",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
        archived = repository.create_ip_asset(
            connection,
            ip_address="10.2.0.2",
            asset_type=IPAssetType.VM,
            project_id=project.id,
        )
        repository.archive_ip_asset(connection, archived.ip_address)
    finally:
        connection.close()

    app.dependency_overrides[ui.get_optional_current_ui_user] = lambda: _user(
        "editor", UserRole.EDITOR
    )
    try:
        unassigned = client.get(
            "/api/ui/ip-assets",
            params={"project_id": "unassigned", "unassigned-only": "true"},
        )
        assigned = client.get(
            "/api/ui/ip-assets",
            params={"assigned-only": "true"},
        )
        archived_response = client.get(
            "/api/ui/ip-assets",
            params={"archived-only": "true"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_optional_current_ui_user, None)

    assert unassigned.status_code == 200
    assert [item["id"] for item in unassigned.json()["assets"]] == [active.id]
    assert unassigned.json()["can_edit"] is True
    assert [item["id"] for item in assigned.json()["assets"]] == [
        assigned_active.id
    ]
    assert assigned.json()["filters"]["normalized"]["assigned_only"] is True
    assert [item["id"] for item in archived_response.json()["assets"]] == [
        archived.id
    ]


def test_ip_assets_mutation_apis_require_editor(client) -> None:
    payload = {
        "ip_address": "10.3.0.1",
        "type": "VM",
        "project_id": None,
        "host_id": None,
        "tags": [],
        "notes": "",
    }

    response = client.post(
        "/api/ui/ip-assets", json=payload, follow_redirects=False
    )

    assert response.status_code in {303, 401, 403}


def test_ip_assets_create_update_auto_host_delete_and_audit_apis(client) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_tag(connection, name="prod")
        project = repository.create_project(connection, name="Core")
        editor = repository.create_user(
            connection,
            username="editor-react",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        created = client.post(
            "/api/ui/ip-assets",
            json={
                "ip_address": "10.4.0.1",
                "type": "BMC",
                "project_id": project.id,
                "host_id": None,
                "tags": ["prod"],
                "notes": "created",
            },
        )
        duplicate = client.post(
            "/api/ui/ip-assets",
            json={
                "ip_address": "10.4.0.1",
                "type": "VM",
                "tags": [],
            },
        )
        invalid = client.post(
            "/api/ui/ip-assets",
            json={
                "ip_address": "invalid",
                "type": "VM",
                "tags": [],
            },
        )
        asset_id = created.json()["asset_id"]
        updated = client.patch(
            f"/api/ui/ip-assets/{asset_id}",
            json={
                "type": "BMC",
                "project_id": None,
                "host_id": None,
                "tags": ["prod"],
                "notes": "updated",
            },
        )
        auto_host = client.post(f"/api/ui/ip-assets/{asset_id}/auto-host")
        rejected_delete = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{asset_id}",
            json={"acknowledged": True, "confirm_ip": "wrong"},
        )
        deleted = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{asset_id}",
            json={"acknowledged": True, "confirm_ip": "10.4.0.1"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert invalid.status_code == 422
    assert updated.status_code == 200
    assert auto_host.status_code == 200
    assert auto_host.json()["host_name"] == "server_10.4.0.1"
    assert rejected_delete.status_code == 400
    assert deleted.status_code == 204

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = repository.list_audit_logs(connection)
    finally:
        connection.close()
    actions = [log.action for log in logs if log.target_label == "10.4.0.1"]
    assert actions == ["DELETE", "UPDATE", "UPDATE", "CREATE"]


def test_ip_assets_bulk_api_validates_and_updates_common_fields(client) -> None:
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_tag(connection, name="prod")
        repository.create_tag(connection, name="edge")
        project = repository.create_project(connection, name="Core")
        editor = repository.create_user(
            connection,
            username="bulk-react",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        first = repository.create_ip_asset(
            connection,
            ip_address="10.5.0.1",
            asset_type=IPAssetType.OS,
            tags=["prod", "edge"],
        )
        second = repository.create_ip_asset(
            connection,
            ip_address="10.5.0.2",
            asset_type=IPAssetType.BMC,
            tags=["prod"],
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        no_selection = client.post(
            "/api/ui/ip-assets/bulk",
            json={"asset_ids": [], "type": "VM"},
        )
        no_change = client.post(
            "/api/ui/ip-assets/bulk",
            json={"asset_ids": [first.id]},
        )
        updated = client.post(
            "/api/ui/ip-assets/bulk",
            json={
                "asset_ids": [first.id, second.id],
                "type": "VM",
                "set_project": True,
                "project_id": project.id,
                "tags_to_remove": ["prod"],
                "notes_mode": "set",
                "notes": "bulk note",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert no_selection.status_code == 422
    assert no_change.status_code == 422
    assert updated.status_code == 200
    assert updated.json()["updated_count"] == 2
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        assets = repository.list_ip_assets_by_ids(connection, [first.id, second.id])
        tags = repository.list_tags_for_ip_assets(
            connection, [first.id, second.id]
        )
    finally:
        connection.close()
    assert all(asset.asset_type == IPAssetType.VM for asset in assets)
    assert all(asset.project_id == project.id for asset in assets)
    assert all(asset.notes == "bulk note" for asset in assets)
    assert tags[first.id] == ["edge"]
    assert tags[second.id] == []
