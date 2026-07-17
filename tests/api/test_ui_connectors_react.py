from __future__ import annotations

import time

import pytest

from app.main import app
from app.models import User, UserRole
from app.routes import ui
from app.routes.ui.connector_routes import api, job_store
from app.routes.ui.connector_routes.common import _redact_connector_logs


CONNECTORS = ("vcenter", "prometheus", "elasticsearch", "cassandra", "ceph", "kubernetes")
VALID_PAYLOADS = {
    "vcenter": {"server": "vc.example", "port": "443", "username": "admin", "password": "v-secret"},
    "prometheus": {"prometheus_url": "http://prom.example:9090", "query": "up", "ip_label": "instance", "token": "p-secret"},
    "elasticsearch": {"elasticsearch_url": "https://es.example:9200", "api_key": "e-secret"},
    "cassandra": {"contact_points": "10.0.0.1,10.0.0.2", "port": "9042", "username": "cass", "password": "c-secret"},
    "ceph": {"ceph_url": "https://ceph.example:8443", "username": "admin", "password": "ceph-secret"},
    "kubernetes": {"api_url": "https://k8s.example:6443", "token": "k-secret"},
}


def _user(role: UserRole) -> User:
    return User(42, role.value.lower(), "x", role, True)


@pytest.fixture(autouse=True)
def clear_jobs():
    with job_store._CONNECTOR_JOB_LOCK:
        job_store._CONNECTOR_JOBS.clear()
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    yield
    app.dependency_overrides.pop(ui.get_current_ui_user, None)


def _mock_runners(monkeypatch, status: str = "completed") -> None:
    def runner(*, job_id: str, **_kwargs) -> None:
        job_store._update_connector_job(
            job_id,
            status=status,
            logs=["Connector completed without credentials."],
            toast_messages=[{"type": "success", "message": "Done."}],
        )

    for name in CONNECTORS:
        monkeypatch.setitem(api.RUNNERS, name, runner)


def test_connectors_react_mount_contains_only_safe_bootstrap_configuration(client) -> None:
    response = client.get("/ui/connectors?tab=kubernetes&job_id=safe-id")
    assert response.status_code == 200
    assert 'id="connectors-root"' in response.text
    assert 'data-endpoint="/api/ui/connectors"' in response.text
    assert 'data-initial-tab="kubernetes"' in response.text
    assert 'data-initial-job-id="safe-id"' in response.text
    assert 'src="/static/react/connectors/connectors.js"' in response.text
    assert "window.location.replace" not in response.text
    assert "password" not in response.text.lower()


def test_invalid_page_tab_defaults_to_overview(client) -> None:
    response = client.get("/ui/connectors?tab=not-a-connector")
    assert response.status_code == 200
    assert 'data-initial-tab="overview"' in response.text


@pytest.mark.parametrize("role,can_apply", [(UserRole.VIEWER, False), (UserRole.EDITOR, True)])
def test_bootstrap_lists_all_connectors_safe_defaults_and_policy(client, role, can_apply) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(role)
    payload = client.get("/api/ui/connectors").json()
    assert [item["name"] for item in payload["connectors"]] == list(CONNECTORS)
    assert payload["asset_types"] == ["OS", "BMC", "VM", "VIP", "OTHER"]
    assert payload["policy"]["can_apply"] is can_apply
    assert payload["poll_interval_ms"] == 1000
    serialized = str(payload).lower()
    for secret in ("v-secret", "p-secret", "e-secret", "c-secret", "ceph-secret", "k-secret"):
        assert secret not in serialized
    for schema in payload["connectors"]:
        for field in schema["fields"]:
            if field["secret"]:
                assert field["default"] == ""


@pytest.mark.parametrize("connector", CONNECTORS)
def test_viewer_can_create_every_dry_run_job_and_poll_sanitized_result(client, monkeypatch, connector) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    _mock_runners(monkeypatch)
    response = client.post(f"/api/ui/connectors/{connector}/run", json={**VALID_PAYLOADS[connector], "mode": "dry-run"})
    assert response.status_code == 202
    started = response.json()
    assert started["connector"] == connector
    assert started["status"] == "queued"
    polled = client.get(started["poll_url"])
    assert polled.status_code == 200
    result = polled.json()
    assert result["status"] == "completed"
    assert result["polling"] is False
    serialized = str(result)
    for value in VALID_PAYLOADS[connector].values():
        if "secret" in str(value):
            assert value not in serialized
    for key in ("password", "token", "api_key"):
        if key in result["form_state"]:
            assert result["form_state"][key] == ""


@pytest.mark.parametrize("connector", CONNECTORS)
def test_viewer_cannot_bypass_apply_permission(client, monkeypatch, connector) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.VIEWER)
    _mock_runners(monkeypatch)
    response = client.post(f"/api/ui/connectors/{connector}/run", json={**VALID_PAYLOADS[connector], "mode": "apply"})
    assert response.status_code == 403
    assert not job_store._CONNECTOR_JOBS


@pytest.mark.parametrize("connector", CONNECTORS)
def test_editor_can_create_every_apply_job(client, monkeypatch, connector) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(UserRole.EDITOR)
    _mock_runners(monkeypatch)
    response = client.post(f"/api/ui/connectors/{connector}/run", json={**VALID_PAYLOADS[connector], "mode": "apply"})
    assert response.status_code == 202


def test_connector_api_rejects_unknown_connector_invalid_mode_ports_and_timeouts(client) -> None:
    assert client.post("/api/ui/connectors/unknown/run", json={}).status_code == 404
    assert client.post("/api/ui/connectors/vcenter/run", json={**VALID_PAYLOADS["vcenter"], "mode": "preview"}).status_code == 400
    port = client.post("/api/ui/connectors/vcenter/run", json={**VALID_PAYLOADS["vcenter"], "port": "70000"})
    assert port.status_code == 400
    assert "Port must be" in str(port.json()["detail"])
    timeout = client.post("/api/ui/connectors/prometheus/run", json={**VALID_PAYLOADS["prometheus"], "timeout": "0"})
    assert timeout.status_code == 400
    assert "Timeout must be" in str(timeout.json()["detail"])


@pytest.mark.parametrize(
    "connector,payload,message",
    [
        ("vcenter", {"server": ""}, "vCenter server is required"),
        ("prometheus", {"prometheus_url": ""}, "Prometheus URL is required"),
        ("elasticsearch", {"elasticsearch_url": "https://es", "username": "u"}, "Password is required"),
        ("cassandra", {"contact_points": ""}, "contact point"),
        ("ceph", {"ceph_url": "", "username": "", "password": ""}, "Ceph Dashboard URL is required"),
        ("kubernetes", {"api_url": "", "token": ""}, "Kubernetes API URL is required"),
    ],
)
def test_connector_specific_validation(client, connector, payload, message) -> None:
    response = client.post(f"/api/ui/connectors/{connector}/run", json=payload)
    assert response.status_code == 400
    assert message.lower() in str(response.json()["detail"]).lower()


@pytest.mark.parametrize("status_value,polling", [("queued", True), ("running", True), ("completed", False), ("failed", False)])
def test_job_polling_reports_all_states(client, status_value, polling) -> None:
    job_id = job_store._create_connector_job(active_tab="prometheus", form_state={"token": "secret", "query": "up"})
    job_store._update_connector_job(job_id, status=status_value, logs=["safe log"])
    payload = client.get(f"/api/ui/connectors/jobs/{job_id}").json()
    assert payload["status"] == status_value
    assert payload["polling"] is polling
    assert payload["form_state"]["token"] == ""
    assert "secret" not in str(payload)


def test_unknown_and_expired_jobs_return_404(client, monkeypatch) -> None:
    assert client.get("/api/ui/connectors/jobs/missing").status_code == 404
    job_id = job_store._create_connector_job(active_tab="ceph", form_state={})
    job_store._CONNECTOR_JOBS[job_id]["updated_at"] = time.time() - 7200
    assert client.get(f"/api/ui/connectors/jobs/{job_id}").status_code == 404


def test_run_scoped_credentials_are_redacted_before_log_storage() -> None:
    assert _redact_connector_logs(
        ["request https://user:top-secret@example.test", "Authorization: top-secret"],
        "top-secret",
    ) == [
        "request https://user:[REDACTED]@example.test",
        "Authorization: [REDACTED]",
    ]


def test_legacy_connector_posts_still_redirect_to_canonical_job_url(client, monkeypatch) -> None:
    monkeypatch.setattr(
        api.vcenter,
        "_run_vcenter_connector",
        lambda **_kwargs: (["safe"], [], 0, 0),
    )
    response = client.post("/ui/connectors/vcenter/run", data={**VALID_PAYLOADS["vcenter"], "mode": "dry-run"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/connectors?tab=vcenter&job_id=")
