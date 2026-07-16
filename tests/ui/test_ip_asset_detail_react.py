from __future__ import annotations

from app import repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def _user(user_id: int, role: UserRole) -> User:
    return User(user_id, role.value.lower(), "x", role, True)


def test_detail_shell_mount_entry_active_nav_and_legacy_routes(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        asset = repository.create_ip_asset(
            connection, ip_address="10.90.0.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(
        1, UserRole.VIEWER
    )
    app.dependency_overrides[ui.require_ui_editor] = lambda: _user(
        2, UserRole.EDITOR
    )
    try:
        detail = client.get(f"/ui/ip-assets/{asset.id}")
        edit = client.get(f"/ui/ip-assets/{asset.id}/edit")
        delete = client.get(f"/ui/ip-assets/{asset.id}/delete")
    finally:
        app.dependency_overrides.clear()

    assert detail.status_code == 200
    assert 'id="ip-asset-detail-root"' in detail.text
    assert f'data-endpoint="/api/ui/ip-assets/{asset.id}"' in detail.text
    assert "/static/react/ip-asset-detail/ip-asset-detail.js" in detail.text
    assert 'class="nav-link nav-link-active" href="/ui/ip-assets"' in detail.text
    assert edit.status_code == 200
    assert delete.status_code == 200


def test_detail_api_requires_authentication_with_correct_return_to(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        asset = repository.create_ip_asset(
            connection, ip_address="10.90.0.11", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    response = client.get(
        f"/api/ui/ip-assets/{asset.id}/detail", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/ui/login?return_to=/api/ui/ip-assets/{asset.id}/detail"
    )


def test_detail_api_payload_includes_pairs_metadata_audit_and_viewer_access(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        project = repository.create_project(
            connection, name="Core", color="#123456"
        )
        host = repository.create_host(connection, name="node-1")
        repository.create_tag(connection, name="prod", color="#ffffff")
        os_asset = repository.create_ip_asset(
            connection,
            ip_address="10.90.1.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
            notes="primary",
            tags=["prod"],
        )
        bmc_asset = repository.create_ip_asset(
            connection,
            ip_address="10.90.1.11",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(
        1, UserRole.VIEWER
    )
    try:
        response = client.get(f"/api/ui/ip-assets/{os_asset.id}/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"]["project_name"] == "Core"
    assert payload["asset"]["project_color"] == "#123456"
    assert payload["asset"]["host_name"] == "node-1"
    assert payload["asset"]["tags"] == [{"name": "prod", "color": "#ffffff"}]
    assert payload["asset"]["host_pair_assets"] == [
        {"id": bmc_asset.id, "ip_address": "10.90.1.11"}
    ]
    assert payload["audit_logs"][0]["user"] == "System"
    assert payload["audit_logs"][0]["action"] == "CREATE"
    assert payload["audit_logs"][0]["changes"]["summary"].startswith("Type: OS")
    assert payload["audit_logs"][0]["changes"]["raw"].startswith(
        "Created IP asset"
    )
    assert payload["metadata"]["types"] == ["OS", "BMC", "VM", "VIP", "OTHER"]
    assert payload["can_edit"] is False
    assert payload["delete_requires_exact_ip"] is True


def test_detail_api_omits_pairs_for_non_host_asset_types(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, name="node-2")
        vm = repository.create_ip_asset(
            connection,
            ip_address="10.90.1.20",
            asset_type=IPAssetType.VM,
            host_id=host.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.90.1.21",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(
        1, UserRole.VIEWER
    )
    try:
        response = client.get(f"/api/ui/ip-assets/{vm.id}/detail")
    finally:
        app.dependency_overrides.clear()
    assert response.json()["asset"]["host_pair_assets"] == []


def test_detail_api_missing_and_archived_are_not_found(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        archived = repository.create_ip_asset(
            connection, ip_address="10.90.2.10", asset_type=IPAssetType.VM
        )
        repository.archive_ip_asset(connection, archived.ip_address)
    finally:
        connection.close()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(
        1, UserRole.VIEWER
    )
    try:
        missing = client.get("/api/ui/ip-assets/999/detail")
        hidden = client.get(f"/api/ui/ip-assets/{archived.id}/detail")
    finally:
        app.dependency_overrides.clear()
    assert missing.status_code == 404
    assert hidden.status_code == 404


def test_detail_api_write_policy_and_edit_clearing_and_validation(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection, "detail-editor", "x", UserRole.EDITOR
        )
        viewer = repository.create_user(
            connection, "detail-viewer", "x", UserRole.VIEWER
        )
        project = repository.create_project(connection, name="Ops")
        host = repository.create_host(connection, name="node-3")
        repository.create_tag(connection, name="edge", color="#000000")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.90.3.10",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: viewer
    try:
        rejected = client.patch(
            f"/api/ui/ip-assets/{asset.id}",
            json={"type": "OS", "project_id": None, "host_id": None, "tags": []},
        )
    finally:
        app.dependency_overrides.clear()
    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        bad_type = client.patch(
            f"/api/ui/ip-assets/{asset.id}",
            json={"type": "BAD", "project_id": None, "host_id": None, "tags": []},
        )
        bad_refs = client.patch(
            f"/api/ui/ip-assets/{asset.id}",
            json={
                "type": "VM",
                "project_id": 999,
                "host_id": 999,
                "tags": ["missing"],
            },
        )
        updated = client.patch(
            f"/api/ui/ip-assets/{asset.id}",
            json={
                "type": "VM",
                "project_id": None,
                "host_id": None,
                "tags": ["edge"],
                "notes": "",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert rejected.status_code == 403
    assert bad_type.status_code == 422
    assert "Asset type is required." in bad_type.json()["detail"]
    assert bad_refs.status_code == 422
    assert "Selected project does not exist." in bad_refs.json()["detail"]
    assert "Selected host does not exist." in bad_refs.json()["detail"]
    assert "Selected tags do not exist: missing." in bad_refs.json()["detail"]
    assert updated.status_code == 200
    connection = _setup_connection()
    try:
        stored = repository.get_ip_asset_by_id(connection, asset.id)
        tags = repository.list_tags_for_ip_assets(connection, [asset.id])[asset.id]
        logs = repository.get_audit_logs_for_ip(connection, asset.id)
    finally:
        connection.close()
    assert stored is not None
    assert stored.project_id is None
    assert stored.host_id is None
    assert stored.asset_type == IPAssetType.VM
    assert tags == ["edge"]
    assert logs[0].username == "detail-editor"
    assert logs[0].action == "UPDATE"


def test_detail_api_auto_host_flag_success_conflict_and_type_errors(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection, "auto-editor", "x", UserRole.EDITOR
        )
        bmc = repository.create_ip_asset(
            connection, ip_address="10.90.4.10", asset_type=IPAssetType.BMC
        )
        vm = repository.create_ip_asset(
            connection, ip_address="10.90.4.11", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "0")
        disabled = client.post(f"/api/ui/ip-assets/{bmc.id}/auto-host")
        monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "1")
        wrong_type = client.post(f"/api/ui/ip-assets/{vm.id}/auto-host")
        created = client.post(f"/api/ui/ip-assets/{bmc.id}/auto-host")
        conflict = client.post(f"/api/ui/ip-assets/{bmc.id}/auto-host")
    finally:
        app.dependency_overrides.clear()

    assert disabled.status_code == 400
    assert disabled.json()["detail"] == "Auto-host creation is disabled."
    assert wrong_type.status_code == 400
    assert created.status_code == 200
    assert created.json()["host_name"] == "server_10.90.4.10"
    assert conflict.status_code == 409


def test_detail_api_delete_low_and_high_risk_confirmations(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection, "delete-editor", "x", UserRole.EDITOR
        )
        project = repository.create_project(connection, name="Critical")
        low = repository.create_ip_asset(
            connection, ip_address="10.90.5.10", asset_type=IPAssetType.VM
        )
        high = repository.create_ip_asset(
            connection,
            ip_address="10.90.5.11",
            asset_type=IPAssetType.VIP,
            project_id=project.id,
        )
    finally:
        connection.close()
    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        no_ack = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{low.id}",
            json={"acknowledged": False, "confirm_ip": ""},
        )
        low_deleted = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{low.id}",
            json={"acknowledged": True, "confirm_ip": ""},
        )
        wrong_ip = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{high.id}",
            json={"acknowledged": True, "confirm_ip": "wrong"},
        )
        high_deleted = client.request(
            "DELETE",
            f"/api/ui/ip-assets/{high.id}",
            json={"acknowledged": True, "confirm_ip": high.ip_address},
        )
    finally:
        app.dependency_overrides.clear()

    assert no_ack.status_code == 400
    assert "Confirm that this delete cannot be undone." in no_ack.json()["detail"]
    assert low_deleted.status_code == 204
    assert wrong_ip.status_code == 400
    assert (
        "Type the exact IP address to delete this high-risk asset."
        in wrong_ip.json()["detail"]
    )
    assert high_deleted.status_code == 204
    connection = _setup_connection()
    try:
        logs = repository.get_audit_logs_for_ip(connection, high.id)
    finally:
        connection.close()
    assert logs[0].action == "DELETE"
    assert logs[0].username == "delete-editor"
