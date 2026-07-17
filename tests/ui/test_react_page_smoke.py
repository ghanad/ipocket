from __future__ import annotations

import pytest

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from tests.react_ui_manifest import REACT_PAGES, ReactPage


@pytest.fixture
def react_page_context(_setup_connection):
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, name="smoke-host")
        asset = repository.create_ip_asset(
            connection,
            ip_address="192.0.2.10",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )
        ip_range = repository.create_ip_range(
            connection, name="smoke-range", cidr="192.0.2.0/24"
        )
    finally:
        connection.close()
    return {
        "host_id": host.id,
        "asset_id": asset.id,
        "range_id": ip_range.id,
    }


@pytest.fixture
def authenticated_react_pages():
    user = User(1, "smoke-admin", "x", UserRole.SUPERUSER, True)
    dependencies = (
        ui.get_current_ui_user,
        ui.get_optional_current_ui_user,
        ui.require_ui_superuser,
    )
    for dependency in dependencies:
        app.dependency_overrides[dependency] = lambda user=user: user
    try:
        yield
    finally:
        for dependency in dependencies:
            app.dependency_overrides.pop(dependency, None)


@pytest.mark.parametrize("page", REACT_PAGES, ids=lambda page: page.entry)
def test_primary_react_page_smoke(
    client,
    page: ReactPage,
    react_page_context,
    authenticated_react_pages,
) -> None:
    route = page.route.format(**react_page_context)
    endpoint = page.endpoint.format(**react_page_context)

    response = client.get(route)

    assert response.status_code == 200
    assert f'id="{page.root_id}"' in response.text
    assert f'data-endpoint="{endpoint}"' in response.text
    assert page.bundle in response.text
    assert page.legacy_marker not in response.text


@pytest.mark.parametrize(
    "page",
    [page for page in REACT_PAGES if page.bootstrap_get],
    ids=lambda page: page.entry,
)
def test_primary_react_bootstrap_api_smoke(
    client,
    page: ReactPage,
    react_page_context,
    authenticated_react_pages,
) -> None:
    response = client.get(page.bootstrap_get.format(**react_page_context))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
