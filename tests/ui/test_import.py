from __future__ import annotations


from app.main import app
from app.models import User, UserRole
from app.routes import ui


def test_import_page_mounts_react_data_operations(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/import")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "Import & Export" in response.text
    assert 'id="data-ops-root"' in response.text
    assert 'data-endpoint="/api/ui/data-ops"' in response.text
    assert 'data-import-endpoint="/api/ui/import"' in response.text
    assert 'data-initial-tab="import"' in response.text
    assert "/static/react/data-ops/data-ops.js" in response.text
    assert 'class="import-options-grid"' not in response.text


def test_export_tab_renders_from_import_page(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/import?tab=export")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert 'id="data-ops-root"' in response.text
    assert 'data-initial-tab="export"' in response.text
    assert "/static/react/data-ops/data-ops.js" in response.text


def test_export_route_renders_unified_data_ops_page(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.get("/ui/export")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "Import & Export" in response.text
    assert 'data-initial-tab="export"' in response.text
