from __future__ import annotations

import sqlite3

from app import repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from app.routes.ui import ranges as ranges_routes


def _editor() -> User:
    return User(1, "editor", "x", UserRole.EDITOR, True)


def test_parse_selected_tags_reports_invalid_tag_name(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        tags, errors = ranges_routes._parse_selected_tags(connection, ["bad tag"])
    finally:
        connection.close()

    assert tags == []
    assert errors == [
        "Tag name may include letters, digits, dash, and underscore only."
    ]


def test_create_range_invalid_cidr_and_duplicate(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        repository.create_ip_range(connection, name="Corp", cidr="10.10.0.0/24")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        invalid_cidr = client.post(
            "/ui/ranges",
            data={"name": "Bad", "cidr": "bad-cidr", "notes": ""},
        )
        duplicate = client.post(
            "/ui/ranges",
            data={"name": "Dup", "cidr": "10.10.0.0/24", "notes": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert invalid_cidr.status_code == 400
    assert "CIDR must be a valid IPv4 network" in invalid_cidr.text
    assert duplicate.status_code == 409
    assert "CIDR already exists." in duplicate.text


def test_create_range_success_redirects(client) -> None:
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        response = client.post(
            "/ui/ranges",
            data={"name": "New Range", "cidr": "10.11.0.0/24", "notes": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/ranges"


def test_edit_update_delete_missing_routes_return_404(client) -> None:
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        edit_get = client.get("/ui/ranges/999/edit")
        edit_post = client.post(
            "/ui/ranges/999/edit",
            data={"name": "x", "cidr": "10.0.0.0/24", "notes": ""},
        )
        delete_get = client.get("/ui/ranges/999/delete")
        delete_post = client.post("/ui/ranges/999/delete", data={"confirm_name": "x"})
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert edit_get.status_code == 404
    assert edit_post.status_code == 404
    assert delete_get.status_code == 404
    assert delete_post.status_code == 404


def test_update_range_invalid_cidr_duplicate_and_not_found_after_update(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        first = repository.create_ip_range(
            connection, name="First", cidr="10.20.0.0/24"
        )
        repository.create_ip_range(connection, name="Second", cidr="10.21.0.0/24")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        invalid_cidr = client.post(
            f"/ui/ranges/{first.id}/edit",
            data={"name": "First", "cidr": "bad", "notes": ""},
        )
        duplicate = client.post(
            f"/ui/ranges/{first.id}/edit",
            data={"name": "First", "cidr": "10.21.0.0/24", "notes": ""},
        )

        monkeypatch.setattr(
            ranges_routes.repository, "update_ip_range", lambda *_args, **_kwargs: None
        )
        missing_after_update = client.post(
            f"/ui/ranges/{first.id}/edit",
            data={"name": "First", "cidr": "10.22.0.0/24", "notes": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert invalid_cidr.status_code == 400
    assert "CIDR must be a valid IPv4 network" in invalid_cidr.text
    assert duplicate.status_code == 409
    assert "CIDR already exists." in duplicate.text
    assert missing_after_update.status_code == 404


def test_delete_range_returns_404_when_delete_repo_returns_false(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        ip_range = repository.create_ip_range(
            connection, name="ToDelete", cidr="10.30.0.0/24"
        )
    finally:
        connection.close()

    monkeypatch.setattr(
        ranges_routes.repository, "delete_ip_range", lambda *_args, **_kwargs: False
    )
    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "ToDelete"},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 404


def test_range_addresses_and_add_validation_branches(client, _setup_connection) -> None:
    connection = _setup_connection()
    try:
        ip_range = repository.create_ip_range(
            connection, name="Lab", cidr="10.40.0.0/29"
        )
        project = repository.create_project(connection, name="Core")
        used_asset = repository.create_ip_asset(
            connection, ip_address="10.40.0.2", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    not_found_page = client.get("/ui/ranges/999/addresses")
    assert not_found_page.status_code == 404

    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        missing_fields = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "", "type": "", "project_id": "", "tags": ""},
        )
        invalid_ip = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "999.1.1.1", "type": "VM", "project_id": ""},
        )
        invalid_type = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "10.40.0.3", "type": "BAD", "project_id": ""},
        )
        missing_type = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "10.40.0.3", "type": "", "project_id": ""},
        )
        invalid_project = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "10.40.0.3", "type": "VM", "project_id": "999"},
        )
        outside_range = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": "10.99.0.3",
                "type": "VM",
                "project_id": str(project.id),
            },
        )
        already_assigned = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": used_asset.ip_address,
                "type": "VM",
                "project_id": str(project.id),
            },
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert missing_fields.status_code == 400
    assert "IP address is required." in missing_fields.text
    assert invalid_ip.status_code == 400
    assert "Invalid IP address." in invalid_ip.text
    assert invalid_type.status_code == 400
    assert "Asset type is required." in invalid_type.text
    assert missing_type.status_code == 400
    assert "Asset type is required." in missing_type.text
    assert invalid_project.status_code == 400
    assert "Selected project does not exist." in invalid_project.text
    assert outside_range.status_code == 400
    assert "IP address is not part of this range." in outside_range.text
    assert already_assigned.status_code == 400
    assert "IP address is already assigned." in already_assigned.text


def test_range_add_handles_missing_range_and_integrity_conflict(
    client, _setup_connection, monkeypatch
) -> None:
    connection = _setup_connection()
    try:
        ip_range = repository.create_ip_range(
            connection, name="Lab2", cidr="10.50.0.0/29"
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        missing_range = client.post(
            "/ui/ranges/999/addresses/add",
            data={"ip_address": "10.50.0.2", "type": "VM", "project_id": ""},
        )

        def _raise_integrity(*_args, **_kwargs):
            raise sqlite3.IntegrityError("duplicate")

        monkeypatch.setattr(
            ranges_routes.repository, "create_ip_asset", _raise_integrity
        )
        conflict = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={"ip_address": "10.50.0.2", "type": "VM", "project_id": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert missing_range.status_code == 404
    assert conflict.status_code == 409
    assert "IP address already exists." in conflict.text


def test_range_quick_edit_not_found_and_validation_branches(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        ip_range = repository.create_ip_range(
            connection, name="EditLab", cidr="10.60.0.0/29"
        )
        outside_asset = repository.create_ip_asset(
            connection, ip_address="10.70.0.2", asset_type=IPAssetType.VM
        )
        in_range_asset = repository.create_ip_asset(
            connection, ip_address="10.60.0.2", asset_type=IPAssetType.VM
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = _editor
    try:
        missing_range = client.post(
            f"/ui/ranges/999/addresses/{in_range_asset.id}/edit",
            data={"type": "VM", "project_id": "", "notes": "", "tags": ""},
        )
        missing_asset = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/999/edit",
            data={"type": "VM", "project_id": "", "notes": "", "tags": ""},
        )
        not_in_range = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{outside_asset.id}/edit",
            data={"type": "VM", "project_id": "", "notes": "", "tags": ""},
        )
        invalid_type = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{in_range_asset.id}/edit",
            data={"type": "BAD", "project_id": "", "notes": "", "tags": ""},
        )
        missing_type = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{in_range_asset.id}/edit",
            data={"type": "", "project_id": "", "notes": "", "tags": ""},
        )
        invalid_project = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{in_range_asset.id}/edit",
            data={"type": "VM", "project_id": "999", "notes": "", "tags": ""},
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert missing_range.status_code == 404
    assert missing_asset.status_code == 404
    assert not_in_range.status_code == 404
    assert invalid_type.status_code == 400
    assert "Asset type is required." in invalid_type.text
    assert missing_type.status_code == 400
    assert "Asset type is required." in missing_type.text
    assert invalid_project.status_code == 400
    assert "Selected project does not exist." in invalid_project.text


def test_range_addresses_js_maps_hash_to_status_query(client) -> None:
    response = client.get("/static/js/range-addresses.js")

    assert response.status_code == 200
    assert '"#used": "used"' in response.text
    assert '"#free": "free"' in response.text
    assert "window.location.replace" in response.text


def test_range_addresses_js_includes_chip_tag_filter_hooks(client) -> None:
    response = client.get("/static/js/range-addresses.js")

    assert response.status_code == 200
    assert "data-range-tag-filter-input" in response.text
    assert "data-range-tag-filter-selected" in response.text
    assert "data-range-remove-tag-filter" in response.text
