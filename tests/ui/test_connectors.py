from __future__ import annotations

import pytest

from app.main import app
from app.models import User, UserRole
from app.routes import ui
from app.routes.ui import connectors as connectors_facade
from app.routes.ui.connector_routes import cassandra, ceph, elasticsearch, kubernetes, prometheus, vcenter


CONNECTOR_CASES = {
    "vcenter": (vcenter, {"server": "vc.example", "username": "admin", "password": "secret", "port": "443"}),
    "prometheus": (prometheus, {"prometheus_url": "http://prom.example:9090", "query": "up", "ip_label": "instance"}),
    "elasticsearch": (elasticsearch, {"elasticsearch_url": "https://es.example:9200"}),
    "cassandra": (cassandra, {"contact_points": "10.0.0.1", "port": "9042"}),
    "ceph": (ceph, {"ceph_url": "https://ceph.example:8443", "username": "admin", "password": "secret"}),
    "kubernetes": (kubernetes, {"api_url": "https://k8s.example:6443", "token": "secret"}),
}


def _user(role: UserRole) -> User:
    return User(10, role.value.lower(), "x", role, True)


def test_connectors_facade_registers_react_api_page_and_legacy_routes() -> None:
    assert [route.path for route in connectors_facade.router.routes] == [
        "/api/ui/connectors",
        "/api/ui/connectors/{connector}/run",
        "/api/ui/connectors/jobs/{job_id}",
        "/ui/connectors",
        "/ui/connectors/vcenter/run",
        "/ui/connectors/prometheus/run",
        "/ui/connectors/elasticsearch/run",
        "/ui/connectors/cassandra/run",
        "/ui/connectors/ceph/run",
        "/ui/connectors/kubernetes/run",
    ]


@pytest.mark.parametrize("tab", ["overview", *CONNECTOR_CASES])
def test_connectors_page_is_react_shell_with_safe_canonical_tab(client, tab) -> None:
    response = client.get(f"/ui/connectors?tab={tab}")
    assert response.status_code == 200
    assert 'id="connectors-root"' in response.text
    assert f'data-initial-tab="{tab}"' in response.text
    assert 'src="/static/react/connectors/connectors.js"' in response.text
    assert "window.location.replace" not in response.text


@pytest.mark.parametrize("connector", CONNECTOR_CASES)
def test_legacy_apply_posts_reject_viewer_for_every_connector(client, connector) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = client.post(
            f"/ui/connectors/{connector}/run",
            data={**CONNECTOR_CASES[connector][1], "mode": "apply"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "secret" not in response.text


@pytest.mark.parametrize("connector", CONNECTOR_CASES)
def test_legacy_dry_run_posts_start_background_job_and_redirect(client, monkeypatch, connector) -> None:
    module, values = CONNECTOR_CASES[connector]
    monkeypatch.setattr(module, f"_run_{connector}_connector", lambda **_kwargs: (["safe result"], [], 0, 0))
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    try:
        response = client.post(
            f"/ui/connectors/{connector}/run",
            data={**values, "mode": "dry-run"},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/ui/connectors?tab={connector}&job_id=")


@pytest.mark.parametrize(
    "connector,expected",
    [
        ("vcenter", "vCenter server is required."),
        ("prometheus", "Prometheus URL is required."),
        ("elasticsearch", "Elasticsearch URL is required."),
        ("cassandra", "contact point"),
        ("ceph", "Ceph Dashboard URL is required."),
        ("kubernetes", "Kubernetes API URL is required."),
    ],
)
def test_legacy_validation_errors_remain_server_rendered(client, connector, expected) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    try:
        response = client.post(f"/ui/connectors/{connector}/run", data={"mode": "dry-run"})
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)
    assert response.status_code == 400
    assert expected.lower() in response.text.lower()
    assert 'type="password"' in response.text
    assert 'value="secret"' not in response.text
