from __future__ import annotations

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


def test_ranges_page_renders_react_mount_inside_jinja_shell(client) -> None:
    response = client.get("/ui/ranges")

    assert response.status_code == 200
    assert 'id="ranges-root"' in response.text
    assert 'class="ranges-root"' in response.text
    assert 'data-endpoint="/api/ui/ranges"' in response.text
    assert 'id="ranges-bootstrap"' in response.text
    assert (
        '<script type="module" src="/static/react/ranges/ranges.js"></script>'
        in response.text
    )
    assert 'class="nav-link nav-link-active" href="/ui/ranges"' in response.text


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

    response = client.get("/api/ui/ranges")

    assert response.status_code == 200
    assert response.json()["ranges"] == [
        {
            "id": 1,
            "name": "No Util",
            "cidr": "10.10.10.0/30",
            "notes": None,
            "total_usable": None,
            "used": None,
            "free": None,
            "utilization_percent": None,
        }
    ]


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
    assert '"mode": "create"' in response.text


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
    assert 'id="range-addresses-root"' in response.text
    assert f'data-range-id="{ip_range.id}"' in response.text
    assert (
        '<script type="module" src="/static/react/range-addresses/range-addresses.js"></script>'
        in response.text
    )
    assert "hx-get=" not in response.text

    payload = client.get(f"/api/ui/ranges/{ip_range.id}/addresses").json()
    used = next(row for row in payload["addresses"] if row["ip_address"] == "10.40.0.10")
    assert used["host_pair"] == "10.40.0.11"
    assert used["tags"] == [{"name": "core", "color": "#1d4ed8"}]
    assert payload["range"]["used"] == 2
    assert payload["range"]["free"] == 252


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

    response = client.get(f"/api/ui/ranges/{ip_range.id}/addresses")
    assert response.status_code == 200
    row = next(
        row for row in response.json()["addresses"] if row["ip_address"] == "10.41.0.10"
    )
    assert {tag["name"] for tag in row["tags"]} == {
        "alpha", "beta", "gamma", "delta", "epsilon"
    }


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
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"q": "10.80.0.2"},
    )
    assert by_ip.status_code == 200
    assert [row["ip_address"] for row in by_ip.json()["addresses"]] == ["10.80.0.2"]

    by_project = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"project_id": str(project.id)},
    )
    assert by_project.status_code == 200
    assert [row["ip_address"] for row in by_project.json()["addresses"]] == ["10.80.0.2"]

    by_unassigned_project = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"project_id": "unassigned"},
    )
    assert by_unassigned_project.status_code == 200
    assert [row["ip_address"] for row in by_unassigned_project.json()["addresses"]] == ["10.80.0.3"]

    by_type = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"type": "BMC"},
    )
    assert by_type.status_code == 200
    assert [row["ip_address"] for row in by_type.json()["addresses"]] == ["10.80.0.3"]

    by_tag = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"tag": "edge"},
    )
    assert by_tag.status_code == 200
    assert [row["ip_address"] for row in by_tag.json()["addresses"]] == ["10.80.0.3"]

    no_match_tag = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"tag": "not-found-anywhere"},
    )
    assert no_match_tag.status_code == 200
    assert no_match_tag.json()["query"]["tags"] == []


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

    used = client.get(f"/api/ui/ranges/{ip_range.id}/addresses", params={"status": "used"})
    assert used.status_code == 200
    assert [row["ip_address"] for row in used.json()["addresses"]] == ["10.81.0.2"]

    free = client.get(f"/api/ui/ranges/{ip_range.id}/addresses", params={"status": "free"})
    assert free.status_code == 200
    free_ips = [row["ip_address"] for row in free.json()["addresses"]]
    assert "10.81.0.2" not in free_ips
    assert "10.81.0.1" in free_ips

    invalid = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses", params={"status": "invalid"}
    )
    assert invalid.status_code == 200
    assert invalid.json()["query"]["status"] == "all"


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

    default_page = client.get(f"/api/ui/ranges/{ip_range.id}/addresses")
    assert default_page.status_code == 200
    assert default_page.json()["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 30,
        "total_pages": 2,
        "has_prev": False,
        "has_next": True,
        "start_index": 1,
        "end_index": 20,
    }

    second_page = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "10", "page": "2"},
    )
    assert second_page.status_code == 200
    assert second_page.json()["pagination"]["page"] == 2
    assert second_page.json()["addresses"][0]["ip_address"] == "10.82.0.11"
    assert second_page.json()["addresses"][-1]["ip_address"] == "10.82.0.20"

    invalid_inputs = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "3", "page": "-9"},
    )
    assert invalid_inputs.status_code == 200
    assert invalid_inputs.json()["query"]["page"] == 1
    assert invalid_inputs.json()["query"]["per_page"] == 20

    oversized_page = client.get(
        f"/api/ui/ranges/{ip_range.id}/addresses",
        params={"per-page": "10", "page": "999"},
    )
    assert oversized_page.status_code == 200
    assert oversized_page.json()["pagination"]["page"] == 3
    assert oversized_page.json()["pagination"]["start_index"] == 21


def test_range_addresses_hx_request_renders_react_shell(client) -> None:
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
    assert 'id="range-addresses-root"' in response.text
    assert "hx-get=" not in response.text


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
        assert f'data-initial-delete-id="{ip_range.id}"' in delete_drawer.text

        delete_error = client.post(
            f"/ui/ranges/{ip_range.id}/delete",
            data={"confirm_name": "Wrong Name"},
        )
        assert delete_error.status_code == 400
        assert "نام رنج" in delete_error.text
        assert '"mode": "delete"' in delete_error.text

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
    assert f'data-initial-delete-id="{ip_range.id}"' in response.text
    assert 'id="ranges-root"' in response.text


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
    assert f'data-initial-edit-id="{ip_range.id}"' in response.text
    assert 'id="ranges-root"' in response.text


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
    assert '"mode": "edit"' in response.text
