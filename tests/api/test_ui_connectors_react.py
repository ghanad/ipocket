from __future__ import annotations

import time

import pytest

from app.main import app
from app.models import User, UserRole
from app.routes import ui
from app.routes.ui.connector_routes import api, cassandra, ceph, elasticsearch, job_store, kubernetes, prometheus, vcenter
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
    assert result["logs"] == ["Connector completed without credentials."]
    assert result["toast_messages"] == [{"type": "success", "message": "Done."}]
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


@pytest.mark.parametrize(
    "connector,payload,expected",
    [
        ("vcenter", {"server": "vc", "username": "u", "password": "p", "port": "444", "insecure": True}, {"server": "vc", "port": 444, "insecure": True}),
        ("prometheus", {"prometheus_url": "http://prom", "query": 'up{job="node"}', "ip_label": "address", "token": "tok"}, {"query": 'up{job="node"}', "ip_label": "address", "token": "tok"}),
        ("elasticsearch", {"elasticsearch_url": "https://es", "api_key": "key", "include_cluster_name_tag": True}, {"api_key": "key", "include_cluster_name_tag": True}),
        ("cassandra", {"contact_points": "10.0.0.1, 10.0.0.2,10.0.0.1", "port": "9142", "username": "u", "password": "p", "use_tls": True, "insecure": True, "include_cluster_name_tag": True}, {"contact_points": ["10.0.0.1", "10.0.0.2"], "port": 9142, "use_tls": True, "insecure": True, "include_cluster_name_tag": True}),
        ("ceph", {"ceph_url": "https://ceph", "username": "u", "password": "p", "include_cluster_name_tag": True, "include_label_tags": True}, {"include_cluster_name_tag": True, "include_label_tags": True}),
        ("kubernetes", {"api_url": "https://k8s", "token": "tok", "cluster_name": "Prod Cluster", "include_cluster_name_tag": True, "include_label_tags": True}, {"cluster_name": "Prod Cluster", "include_cluster_name_tag": True, "include_label_tags": True}),
    ],
)
def test_connector_api_propagates_connector_specific_mapping(client, monkeypatch, connector, payload, expected) -> None:
    captured: dict[str, object] = {}

    def runner(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(api.RUNNERS, connector, runner)
    response = client.post(f"/api/ui/connectors/{connector}/run", json={**payload, "mode": "dry-run"})
    assert response.status_code == 202
    for key, value in expected.items():
        assert captured[key] == value


@pytest.mark.parametrize(
    "connector,payload,message",
    [
        ("elasticsearch", {"elasticsearch_url": "https://es", "api_key": "key", "username": "u", "password": "p"}, "not both"),
        ("elasticsearch", {"elasticsearch_url": "https://es", "username": "u"}, "Password is required"),
        ("elasticsearch", {"elasticsearch_url": "https://es", "password": "p"}, "Username is required"),
        ("cassandra", {"contact_points": "10.0.0.1", "username": "u"}, "Password is required"),
        ("cassandra", {"contact_points": "10.0.0.1", "password": "p"}, "Username is required"),
        ("cassandra", {"contact_points": "10.0.0.1", "insecure": True}, "requires TLS"),
        ("cassandra", {"contact_points": "10.0.0.1", "port": "0"}, "Port must be"),
        ("cassandra", {"contact_points": "10.0.0.1", "timeout": "0"}, "Timeout must be"),
        ("ceph", {"ceph_url": "https://ceph", "username": "u", "password": "p", "timeout": "0"}, "Timeout must be"),
        ("kubernetes", {"api_url": "", "token": ""}, "Kubernetes API URL is required"),
    ],
)
def test_connector_api_retains_auth_tls_and_numeric_validation(client, connector, payload, message) -> None:
    response = client.post(f"/api/ui/connectors/{connector}/run", json={**payload, "mode": "dry-run"})
    assert response.status_code == 400
    assert message.lower() in str(response.json()["detail"]).lower()


@pytest.mark.parametrize("payload", [
    {"elasticsearch_url": "https://es"},
    {"elasticsearch_url": "https://es", "api_key": "key"},
    {"elasticsearch_url": "https://es", "username": "u", "password": "p"},
])
def test_elasticsearch_optional_authentication_combinations_are_accepted(client, monkeypatch, payload) -> None:
    monkeypatch.setitem(api.RUNNERS, "elasticsearch", lambda **_kwargs: None)
    assert client.post("/api/ui/connectors/elasticsearch/run", json={**payload, "mode": "dry-run"}).status_code == 202


@pytest.mark.parametrize(
    "module,error_name,job_name,kwargs,secret",
    [
        (vcenter, "VCenterConnectorError", "_run_vcenter_connector_job", {"server": "vc", "username": "u", "password": "v-secret", "port": 443, "insecure": False}, "v-secret"),
        (prometheus, "PrometheusConnectorError", "_run_prometheus_connector_job", {"prometheus_url": "http://prom", "query": "up", "ip_label": "instance", "asset_type": "OTHER", "project_name": None, "tags": None, "token": "p-secret", "insecure": False, "timeout": 30}, "p-secret"),
        (elasticsearch, "ElasticsearchConnectorError", "_run_elasticsearch_connector_job", {"elasticsearch_url": "https://es", "username": None, "password": "e-secret", "api_key": None, "asset_type": "OTHER", "project_name": None, "tags": None, "note": None, "include_cluster_name_tag": False, "timeout": 30}, "e-secret"),
        (cassandra, "CassandraConnectorError", "_run_cassandra_connector_job", {"contact_points": ["10.0.0.1"], "port": 9042, "username": "u", "password": "c-secret", "use_tls": False, "insecure": False, "asset_type": "OTHER", "project_name": None, "tags": None, "note": None, "include_cluster_name_tag": False, "timeout": 30}, "c-secret"),
        (ceph, "CephConnectorError", "_run_ceph_connector_job", {"ceph_url": "https://ceph", "username": "u", "password": "ceph-secret", "insecure": False, "asset_type": "OTHER", "project_name": None, "tags": None, "note": None, "include_cluster_name_tag": False, "include_label_tags": False, "timeout": 30}, "ceph-secret"),
        (kubernetes, "KubernetesConnectorError", "_run_kubernetes_connector_job", {"api_url": "https://k8s", "token": "k-secret", "insecure": False, "asset_type": "OS", "project_name": None, "tags": None, "note": None, "cluster_name": None, "include_cluster_name_tag": False, "include_label_tags": False, "timeout": 30}, "k-secret"),
    ],
)
def test_connector_job_failures_are_safe_and_redact_credentials(monkeypatch, module, error_name, job_name, kwargs, secret, tmp_path) -> None:
    job_id = job_store._create_connector_job(active_tab=module.__name__.rsplit(".", 1)[-1], form_state={})
    error_type = getattr(module, error_name)
    monkeypatch.setattr(module, f"_run_{module.__name__.rsplit('.', 1)[-1]}_connector", lambda **_kwargs: (_ for _ in ()).throw(error_type(f"failure {secret}")))
    getattr(module, job_name)(job_id=job_id, db_path=str(tmp_path / "jobs.db"), user_id=None, mode="dry-run", **kwargs)
    result = job_store._get_connector_job(job_id)
    assert result is not None
    assert result["status"] == "failed"
    assert result["logs"] == ["Connector failed. Review server logs for details."]
    assert result["toast_messages"][0]["type"] == "error"
    assert secret not in str(result)


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
    assert job_id not in job_store._CONNECTOR_JOBS


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
