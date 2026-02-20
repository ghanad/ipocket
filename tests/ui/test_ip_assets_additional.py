from __future__ import annotations

from app import repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from app.routes.ui import ip_assets as ip_assets_routes


def _editor_user() -> User:
    return User(1, "editor", "x", UserRole.EDITOR, True)


def _viewer_user() -> User:
    return User(2, "viewer", "x", UserRole.VIEWER, True)


def test_friendly_audit_changes_and_tag_validation_helper(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        empty = ip_assets_routes._friendly_audit_changes("")
        plain = ip_assets_routes._friendly_audit_changes("updated fields")
        _, errors = ip_assets_routes._parse_selected_tags(connection, ["bad tag name"])
    finally:
        connection.close()

    assert empty == {"summary": "No additional details.", "raw": ""}
    assert plain == {"summary": "updated fields", "raw": "updated fields"}
    assert errors == [
        "Tag name may include letters, digits, dash, and underscore only."
    ]


def test_delete_requires_exact_ip_for_high_risk_inputs(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        vip_asset = repository.create_ip_asset(
            connection, ip_address="10.81.0.30", asset_type=IPAssetType.VIP
        )
        vm_asset = repository.create_ip_asset(
            connection, ip_address="10.81.0.31", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    assert ip_assets_routes._delete_requires_exact_ip(vip_asset, []) is True
    assert ip_assets_routes._delete_requires_exact_ip(vm_asset, ["production"]) is True
    assert ip_assets_routes._delete_requires_exact_ip(vm_asset, []) is False


def test_ip_assets_list_handles_invalid_filters_and_delete_toasts(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        repository.create_ip_asset(
            connection, ip_address="10.81.0.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    response = client.get(
        "/ui/ip-assets",
        params={
            "per-page": "15",
            "type": "INVALID",
            "tag": "bad tag",
            "delete-error": "failed",
            "delete-success": "done",
        },
    )

    assert response.status_code == 200
    assert "failed" in response.text
    assert "done" in response.text


def test_ip_assets_list_pagination_query_includes_selected_filters(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        project = repository.create_project(connection, name="core")
        repository.create_ip_asset(
            connection,
            ip_address="10.81.0.20",
            asset_type=IPAssetType.VIP,
            project_id=project.id,
        )
    finally:
        connection.close()

    response = client.get(
        "/ui/ip-assets",
        params={
            "project_id": str(project.id),
            "type": "VIP",
            "unassigned-only": "true",
            "archived-only": "true",
        },
    )

    assert response.status_code == 200


def test_bulk_edit_validates_invalid_ids_type_and_project_selection(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection,
            username="editor-bulk",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        asset = repository.create_ip_asset(
            connection, ip_address="10.81.1.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        bad_id = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[("asset_ids", "abc"), ("type", "VIP")],
            follow_redirects=False,
        )
        bad_type = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[("asset_ids", str(asset.id)), ("type", "BAD")],
            follow_redirects=False,
        )
        missing_project = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[("asset_ids", str(asset.id)), ("project_id", "999")],
            follow_redirects=False,
        )
        unassign_project = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[("asset_ids", str(asset.id)), ("project_id", "unassigned")],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert bad_id.status_code == 303
    assert "bulk-error=Select+valid+IP+assets." in bad_id.headers["location"]
    assert bad_type.status_code == 303
    assert "bulk-error=Select+a+valid+type." in bad_type.headers["location"]
    assert missing_project.status_code == 303
    assert (
        "bulk-error=Selected+project+does+not+exist."
        in missing_project.headers["location"]
    )
    assert unassign_project.status_code == 303
    assert "bulk-success=Updated+1+IP+assets." in unassign_project.headers["location"]


def test_create_ip_validation_paths_and_duplicate_conflict(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, name="host-a")
        repository.create_ip_asset(
            connection, ip_address="10.81.2.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor_user
    try:
        missing_ip_and_bad_type = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "", "type": "BAD", "host_id": "999"},
        )
        invalid_ip = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "999.1.1.1", "type": "VM"},
        )
        missing_type = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "10.81.2.11", "type": ""},
        )
        duplicate = client.post(
            "/ui/ip-assets/new",
            data={
                "ip_address": "10.81.2.10",
                "type": "VM",
                "host_id": str(host.id),
            },
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert missing_ip_and_bad_type.status_code == 400
    assert "IP address is required." in missing_ip_and_bad_type.text
    assert "Asset type is required." in missing_ip_and_bad_type.text
    assert "Selected host does not exist." in missing_ip_and_bad_type.text
    assert invalid_ip.status_code == 400
    assert "Invalid IP address." in invalid_ip.text
    assert missing_type.status_code == 400
    assert "Asset type is required." in missing_type.text
    assert duplicate.status_code == 409
    assert "IP address already exists." in duplicate.text


def test_create_ip_reuses_archived_record_in_ui_form(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection,
            username="editor-restore",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        archived = repository.create_ip_asset(
            connection, ip_address="10.81.2.50", asset_type=IPAssetType.VM
        )
        repository.archive_ip_asset(connection, archived.ip_address)
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        restored = client.post(
            "/ui/ip-assets/new",
            data={"ip_address": "10.81.2.50", "type": "OS"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert restored.status_code == 303
    assert restored.headers["location"] == "/ui/ip-assets"

    verify_connection = _setup_connection()
    try:
        refreshed = repository.get_ip_asset_by_ip(verify_connection, "10.81.2.50")
    finally:
        verify_connection.close()

    assert refreshed is not None
    assert refreshed.id == archived.id
    assert refreshed.archived is False
    assert refreshed.asset_type == IPAssetType.OS


def test_detail_edit_auto_host_and_edit_submit_edge_paths(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection, username="editor-a", hashed_password="x", role=UserRole.EDITOR
        )
        viewer = repository.create_user(
            connection, username="viewer-a", hashed_password="x", role=UserRole.VIEWER
        )
        archived = repository.create_ip_asset(
            connection, ip_address="10.81.3.10", asset_type=IPAssetType.BMC
        )
        repository.archive_ip_asset(connection, archived.ip_address)
        vm_asset = repository.create_ip_asset(
            connection, ip_address="10.81.3.11", asset_type=IPAssetType.VM
        )
        editable = repository.create_ip_asset(
            connection, ip_address="10.81.3.12", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: viewer
    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        detail_archived = client.get(f"/ui/ip-assets/{archived.id}")
        edit_archived = client.get(f"/ui/ip-assets/{archived.id}/edit")
        auto_host_archived = client.post(f"/ui/ip-assets/{archived.id}/auto-host")
        auto_host_non_bmc = client.post(f"/ui/ip-assets/{vm_asset.id}/auto-host")

        edit_missing = client.post("/ui/ip-assets/999/edit", data={"type": "VM"})
        edit_invalid = client.post(
            f"/ui/ip-assets/{editable.id}/edit",
            data={"type": "BAD", "host_id": "999"},
        )
        edit_missing_type = client.post(
            f"/ui/ip-assets/{editable.id}/edit",
            data={"type": ""},
        )
        edit_success_default_redirect = client.post(
            f"/ui/ip-assets/{editable.id}/edit",
            data={"type": "VIP", "host_id": "", "project_id": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert detail_archived.status_code == 404
    assert edit_archived.status_code == 404
    assert auto_host_archived.status_code == 404
    assert auto_host_non_bmc.status_code == 400
    assert (
        auto_host_non_bmc.json()["error"]
        == "Auto-host creation is only available for BMC assets."
    )
    assert edit_missing.status_code == 404
    assert edit_invalid.status_code == 400
    assert "Asset type is required." in edit_invalid.text
    assert "Selected host does not exist." in edit_invalid.text
    assert edit_missing_type.status_code == 400
    assert edit_success_default_redirect.status_code == 303
    assert edit_success_default_redirect.headers["location"].endswith(
        f"/ui/ip-assets/{editable.id}"
    )


def test_delete_and_archive_non_json_redirect_and_not_found_paths(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        editor = repository.create_user(
            connection, username="editor-b", hashed_password="x", role=UserRole.EDITOR
        )
        low_risk = repository.create_ip_asset(
            connection, ip_address="10.81.4.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: editor
    try:
        delete_confirm_missing = client.get("/ui/ip-assets/999/delete")
        delete_missing = client.post(
            "/ui/ip-assets/999/delete", data={"confirm_delete_ack": "on"}
        )

        delete_error_redirect = client.post(
            f"/ui/ip-assets/{low_risk.id}/delete",
            data={"confirm_delete_ack": "", "return_to": "/ui/ip-assets"},
            follow_redirects=False,
        )
        delete_success_redirect = client.post(
            f"/ui/ip-assets/{low_risk.id}/delete",
            data={"confirm_delete_ack": "on", "return_to": "/ui/ip-assets"},
            follow_redirects=False,
        )

        archive_missing = client.post("/ui/ip-assets/999/archive")

        connection = _setup_connection()
        try:
            archivable = repository.create_ip_asset(
                connection, ip_address="10.81.4.20", asset_type=IPAssetType.VM
            )
        finally:
            connection.close()

        archive_success = client.post(
            f"/ui/ip-assets/{archivable.id}/archive", follow_redirects=False
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert delete_confirm_missing.status_code == 404
    assert delete_missing.status_code == 404
    assert delete_error_redirect.status_code == 303
    assert (
        "delete-error=Confirm+that+this+delete+cannot+be+undone."
        in delete_error_redirect.headers["location"]
    )
    assert delete_success_redirect.status_code == 303
    assert (
        "delete-success=Deleted+10.81.4.10."
        in delete_success_redirect.headers["location"]
    )
    assert archive_missing.status_code == 404
    assert archive_success.status_code == 303
    assert archive_success.headers["location"] == "/ui/ip-assets"


def test_delete_confirm_page_renders_for_existing_asset(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        repository.create_user(
            connection,
            username="editor-confirm",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        asset = repository.create_ip_asset(
            connection, ip_address="10.81.5.10", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor_user
    try:
        response = client.get(f"/ui/ip-assets/{asset.id}/delete")
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 200
    assert "Confirm IP Delete" in response.text


def test_bulk_edit_project_id_parse_none_branch(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        asset = repository.create_ip_asset(
            connection, ip_address="10.81.5.20", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    monkeypatch.setattr(ip_assets_routes, "_parse_optional_int", lambda _value: None)
    app.dependency_overrides[ui.require_ui_editor] = _editor_user
    try:
        response = client.post(
            "/ui/ip-assets/bulk-edit",
            data=[("asset_ids", str(asset.id)), ("project_id", "123")],
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert "bulk-error=Select+a+valid+project." in response.headers["location"]
