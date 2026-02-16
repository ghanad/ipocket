from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def test_ranges_page_renders_single_combined_ranges_table(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Corp LAN", cidr="192.168.10.0/24"
        )
    finally:
        connection.close()

    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert "data-range-add" in response.text
    assert "Add IP Range" in response.text
    assert "data-range-create-drawer" in response.text
    assert "192.168.10.0/24" in response.text
    assert "Saved ranges" not in response.text
    assert "Subnet Utilization" not in response.text
    assert "<h2>IP Ranges</h2>" in response.text
    assert "Total usable" in response.text
    assert "Used" in response.text
    assert "Free" in response.text
    assert "Utilization" in response.text
    assert "Actions" in response.text
    assert "Created" not in response.text
    assert (
        f'href="/ui/ranges/{ip_range.id}/addresses?status=used#used"' in response.text
    )
    assert (
        f'href="/ui/ranges/{ip_range.id}/addresses?status=free#free"' in response.text
    )
    assert 'class="btn btn-secondary btn-small"' in response.text
    assert 'class="btn btn-danger btn-small"' in response.text
    assert "data-range-edit" in response.text
    assert "data-range-delete" in response.text
    assert 'data-range-delete-cidr="192.168.10.0/24"' in response.text
    assert "data-range-delete-cidr-display" in response.text
    assert "data-range-delete-used-display" in response.text
    assert "data-range-delete-drawer" in response.text


def test_ranges_page_shows_em_dash_when_utilization_missing(
    client, monkeypatch
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        repository.create_ip_range(connection, name="No Util", cidr="10.10.10.0/30")
    finally:
        connection.close()

    from app.routes.ui import ranges as ranges_ui

    monkeypatch.setattr(
        ranges_ui.repository, "get_ip_range_utilization", lambda _connection: []
    )

    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert "No Util" in response.text
    assert "—" in response.text


def test_ranges_page_reopens_create_drawer_with_errors(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection, username="editor", hashed_password="x", role=UserRole.EDITOR
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            "/ui/ranges",
            data={"name": "", "cidr": "", "notes": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Range name is required." in response.text
    assert "CIDR is required." in response.text
    assert 'data-range-open="true"' in response.text


def test_range_addresses_page_shows_tags(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Lab Range", cidr="10.40.0.0/24"
        )
        host = repository.create_host(connection, name="lab-01")
        repository.create_tag(connection, name="core", color="#1d4ed8")
        repository.create_ip_asset(
            connection,
            ip_address="10.40.0.10",
            asset_type=IPAssetType.OS,
            tags=["core"],
            host_id=host.id,
            notes="primary",
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.40.0.11",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ranges/{ip_range.id}/addresses")

    assert response.status_code == 200
    assert "Addresses in this range" in response.text
    assert "Host Pair" in response.text
    assert "core" in response.text
    assert "tag-color" in response.text
    assert "10.40.0.11" in response.text
    assert "Add…" in response.text
    assert "Edit" in response.text
    assert "data-range-drawer" in response.text
    assert "data-tag-picker" in response.text
    assert "Allocate next" not in response.text
    assert 'name="q"' in response.text
    assert 'name="project_id"' in response.text
    assert 'name="type"' in response.text
    assert "data-range-tag-filter-input" in response.text
    assert "data-range-tag-filter-selected" in response.text


def test_range_addresses_tags_cell_collapses_after_three_with_more_trigger(
    client,
) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Dense Tag Range", cidr="10.41.0.0/24"
        )
        for name, color in [
            ("alpha", "#1d4ed8"),
            ("beta", "#0f766e"),
            ("gamma", "#92400e"),
            ("delta", "#7c3aed"),
            ("epsilon", "#b91c1c"),
        ]:
            repository.create_tag(connection, name=name, color=color)
        repository.create_ip_asset(
            connection,
            ip_address="10.41.0.10",
            asset_type=IPAssetType.VM,
            tags=["alpha", "beta", "gamma", "delta", "epsilon"],
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ranges/{ip_range.id}/addresses")

    assert response.status_code == 200
    assert '<td class="ip-tags-cell">' in response.text
    assert "alpha" in response.text
    assert "beta" in response.text
    assert "gamma" in response.text
    assert 'data-range-quick-filter-tag="alpha"' in response.text
    assert "data-tags-more-toggle" in response.text
    assert 'data-tags-ip="10.41.0.10"' in response.text
    assert "+2 more" in response.text

    range_addresses_js = (
        Path(__file__).resolve().parents[2] / "app/static/js/range-addresses.js"
    )
    js_source = range_addresses_js.read_text(encoding="utf-8")
    assert "data-tags-popover-search" in js_source
    assert "data-tags-more-toggle" in js_source
    assert "data-range-quick-filter-tag" in js_source


def test_range_addresses_filters_by_ip_project_type_and_tag(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Search Range", cidr="10.80.0.0/29"
        )
        project = repository.create_project(connection, name="Core")
        host = repository.create_host(connection, name="core-01")
        repository.create_tag(connection, name="core")
        repository.create_tag(connection, name="edge")
        repository.create_ip_asset(
            connection,
            ip_address="10.80.0.2",
            asset_type=IPAssetType.OS,
            project_id=project.id,
            host_id=host.id,
            notes="primary note",
            tags=["core"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.80.0.3",
            asset_type=IPAssetType.BMC,
            host_id=host.id,
            notes="secondary",
            tags=["edge"],
        )
    finally:
        connection.close()

    by_ip = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"q": "10.80.0.2"},
    )
    assert by_ip.status_code == 200
    assert 'id="ip-10-80-0-2"' in by_ip.text
    assert 'id="ip-10-80-0-3"' not in by_ip.text

    by_project = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"project_id": str(project.id)},
    )
    assert by_project.status_code == 200
    assert 'id="ip-10-80-0-2"' in by_project.text
    assert 'id="ip-10-80-0-3"' not in by_project.text

    by_unassigned_project = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"project_id": "unassigned"},
    )
    assert by_unassigned_project.status_code == 200
    assert 'id="ip-10-80-0-3"' in by_unassigned_project.text
    assert 'id="ip-10-80-0-2"' not in by_unassigned_project.text

    by_type = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"type": "BMC"},
    )
    assert by_type.status_code == 200
    assert 'id="ip-10-80-0-3"' in by_type.text
    assert 'id="ip-10-80-0-2"' not in by_type.text

    by_tag = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"tag": "edge"},
    )
    assert by_tag.status_code == 200
    assert 'id="ip-10-80-0-3"' in by_tag.text
    assert 'id="ip-10-80-0-2"' not in by_tag.text

    no_match_tag = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"tag": "not-found-anywhere"},
    )
    assert no_match_tag.status_code == 200
    assert "No addresses in this range." in no_match_tag.text


def test_range_addresses_status_filter_supports_used_free_and_invalid(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Status Range", cidr="10.81.0.0/29"
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.81.0.2",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    used = client.get(f"/ui/ranges/{ip_range.id}/addresses", params={"status": "used"})
    assert used.status_code == 200
    assert "10.81.0.2" in used.text
    assert "10.81.0.1" not in used.text

    free = client.get(f"/ui/ranges/{ip_range.id}/addresses", params={"status": "free"})
    assert free.status_code == 200
    assert "10.81.0.2" not in free.text
    assert "10.81.0.1" in free.text

    invalid = client.get(
        f"/ui/ranges/{ip_range.id}/addresses", params={"status": "invalid"}
    )
    assert invalid.status_code == 200
    assert "10.81.0.2" in invalid.text
    assert "10.81.0.1" in invalid.text


def test_range_addresses_pagination_and_bounds(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Paging Range", cidr="10.82.0.0/27"
        )
    finally:
        connection.close()

    default_page = client.get(f"/ui/ranges/{ip_range.id}/addresses")
    assert default_page.status_code == 200
    assert "Showing 1-20 of 30" in default_page.text
    assert "Previous" in default_page.text
    assert "Next" in default_page.text

    second_page = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "10", "page": "2"},
    )
    assert second_page.status_code == 200
    assert "Showing 11-20 of 30" in second_page.text
    assert "Page 2 of 3" in second_page.text
    assert "10.82.0.11" in second_page.text
    assert "10.82.0.20" in second_page.text
    assert ">10.82.0.1<" not in second_page.text

    invalid_inputs = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "3", "page": "-9"},
    )
    assert invalid_inputs.status_code == 200
    assert "Showing 1-20 of 30" in invalid_inputs.text

    oversized_page = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "10", "page": "999"},
    )
    assert oversized_page.status_code == 200
    assert "Showing 21-30 of 30" in oversized_page.text
    assert "Page 3 of 3" in oversized_page.text


def test_range_addresses_hx_request_renders_partial_table_only(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="HTMX Range", cidr="10.83.0.0/29"
        )
    finally:
        connection.close()

    response = client.get(
        f"/ui/ranges/{ip_range.id}/addresses",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "Addresses in this range" in response.text
    assert "Back to ranges" not in response.text
    assert "<h1>" not in response.text


def test_range_addresses_quick_add_creates_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection, username="editor", hashed_password="x", role=UserRole.EDITOR
        )
        ip_range = repository.create_ip_range(
            connection, name="Edge Range", cidr="10.60.0.0/29"
        )
        project = repository.create_project(connection, name="Edge")
        repository.create_tag(connection, name="edge")
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": "10.60.0.2",
                "type": "VM",
                "project_id": str(project.id),
                "notes": "allocated from range",
                "tags": ["edge"],
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/ui/ranges/{ip_range.id}/addresses#ip-10-60-0-2"
    )

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        asset = repository.get_ip_asset_by_ip(connection, "10.60.0.2")
        assert asset is not None
        assert asset.project_id == project.id
        assert asset.notes == "allocated from range"
        assert repository.list_tags_for_ip_assets(connection, [asset.id])[asset.id] == [
            "edge"
        ]
    finally:
        connection.close()


def test_range_addresses_quick_edit_updates_asset(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection, username="editor", hashed_password="x", role=UserRole.EDITOR
        )
        ip_range = repository.create_ip_range(
            connection, name="Edge Range", cidr="10.61.0.0/29"
        )
        project = repository.create_project(connection, name="Core")
        repository.create_tag(connection, name="mgmt")
        asset = repository.create_ip_asset(
            connection,
            ip_address="10.61.0.2",
            asset_type=IPAssetType.VM,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/{asset.id}/edit",
            data={
                "type": "BMC",
                "project_id": str(project.id),
                "notes": "updated",
                "tags": ["mgmt"],
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/ui/ranges/{ip_range.id}/addresses#ip-10-61-0-2"
    )

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        updated = repository.get_ip_asset_by_ip(connection, "10.61.0.2")
        assert updated is not None
        assert updated.asset_type == IPAssetType.BMC
        assert updated.project_id == project.id
        assert updated.notes == "updated"
        assert repository.list_tags_for_ip_assets(connection, [updated.id])[
            updated.id
        ] == ["mgmt"]
    finally:
        connection.close()


def test_range_addresses_quick_add_rejects_nonexistent_tag_selection(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection, username="editor", hashed_password="x", role=UserRole.EDITOR
        )
        ip_range = repository.create_ip_range(
            connection, name="Fail Range", cidr="10.62.0.0/29"
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/addresses/add",
            data={
                "ip_address": "10.62.0.2",
                "type": "VM",
                "project_id": "",
                "notes": "",
                "tags": "ghost",
            },
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Selected tags do not exist: ghost." in response.text


def test_ranges_edit_and_delete_flow(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Corp LAN", cidr="192.168.10.0/24"
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "editor", "x", UserRole.EDITOR, True
    )
    try:
        edit_response = client.get(
            f"/ui/ranges/{ip_range.id}/edit", follow_redirects=False
        )
        assert edit_response.status_code == 303
        assert edit_response.headers["location"].endswith(
            f"/ui/ranges?edit={ip_range.id}"
        )

        update_response = client.post(
            f"/ui/ranges/{ip_range.id}/edit",
            data={
                "name": "Corporate LAN",
                "cidr": "192.168.20.0/24",
                "notes": "updated",
            },
            follow_redirects=False,
        )
        assert update_response.status_code == 303

        delete_confirm = client.get(
            f"/ui/ranges/{ip_range.id}/delete", follow_redirects=False
        )
        assert delete_confirm.status_code == 303
        assert delete_confirm.headers["location"].endswith(
            f"/ui/ranges?delete={ip_range.id}"
        )

        delete_drawer = client.get(f"/ui/ranges?delete={ip_range.id}")
        assert delete_drawer.status_code == 200
        assert 'data-range-delete-open="true"' in delete_drawer.text
        assert f'action="/ui/ranges/{ip_range.id}/delete"' in delete_drawer.text

        delete_error = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Wrong Name"},
        )
        assert delete_error.status_code == 400
        assert "نام رنج" in delete_error.text
        assert 'data-range-delete-open="true"' in delete_error.text

        delete_response = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Corporate LAN"},
            follow_redirects=False,
        )
        assert delete_response.status_code == 303
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_ranges_page_opens_delete_drawer_from_query_param(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Delete Me", cidr="10.30.0.0/24"
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ranges?delete={ip_range.id}")

    assert response.status_code == 200
    assert "data-range-delete-drawer" in response.text
    assert 'data-range-delete-open="true"' in response.text
    assert f'data-range-delete-id="{ip_range.id}"' in response.text
    assert f'action="/ui/ranges/{ip_range.id}/delete"' in response.text


def test_ranges_page_opens_edit_drawer_from_query_param(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        ip_range = repository.create_ip_range(
            connection, name="Corp LAN", cidr="192.168.10.0/24", notes="initial"
        )
    finally:
        connection.close()

    response = client.get(f"/ui/ranges?edit={ip_range.id}")

    assert response.status_code == 200
    assert "data-range-edit-drawer" in response.text
    assert f'data-range-edit-id="{ip_range.id}"' in response.text
    assert f'action="/ui/ranges/{ip_range.id}/edit"' in response.text
    assert 'value="Corp LAN"' in response.text


def test_range_edit_error_reopens_edit_drawer(client) -> None:
    import os
    from app import db, repository

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        user = repository.create_user(
            connection, username="editor", hashed_password="x", role=UserRole.EDITOR
        )
        ip_range = repository.create_ip_range(
            connection, name="Corp LAN", cidr="192.168.10.0/24"
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.require_ui_editor] = lambda: user
    try:
        response = client.post(
            f"/ui/ranges/{ip_range.id}/edit",
            data={"name": "", "cidr": "", "notes": ""},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.require_ui_editor, None)

    assert response.status_code == 400
    assert "Range name is required." in response.text
    assert "CIDR is required." in response.text
    assert 'data-range-edit-open="true"' in response.text
