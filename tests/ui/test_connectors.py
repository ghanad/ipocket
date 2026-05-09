from __future__ import annotations

import time

from app import db, repository
from app.connectors.cassandra import CassandraNodeRecord
from app.connectors.ceph import CephHostRecord
from app.connectors.elasticsearch import ElasticsearchNodeRecord
from app.connectors.kubernetes import KubernetesNodeRecord
from app.connectors.prometheus import PrometheusMetricRecord
from app.connectors.vcenter import VCenterHostRecord, VCenterVmRecord
from app.imports.models import ImportApplyResult, ImportEntitySummary, ImportSummary
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui
from app.routes.ui import connectors as connectors_routes


def _resolve_connector_response(client, response):
    if response.status_code != 303:
        return response
    return client.get(response.headers["location"])


def test_connectors_page_renders_sidebar_link_and_tabs(client) -> None:
    response = client.get("/ui/connectors")

    assert response.status_code == 200
    assert 'href="/ui/connectors"' in response.text
    assert "Integrations" in response.text
    assert 'href="/ui/connectors?tab=overview"' in response.text
    assert 'href="/ui/connectors?tab=vcenter"' in response.text
    assert 'href="/ui/connectors?tab=prometheus"' in response.text
    assert 'href="/ui/connectors?tab=elasticsearch"' in response.text
    assert 'href="/ui/connectors?tab=cassandra"' in response.text
    assert 'href="/ui/connectors?tab=ceph"' in response.text
    assert 'href="/ui/connectors?tab=kubernetes"' in response.text
    assert "Available Connectors" in response.text
    assert "vCenter" in response.text
    assert "Prometheus" in response.text
    assert "Elasticsearch" in response.text
    assert "Cassandra" in response.text
    assert "Ceph" in response.text
    assert "Kubernetes" in response.text


def test_connectors_vcenter_tab_renders_connector_commands(client) -> None:
    response = client.get("/ui/connectors?tab=vcenter")

    assert response.status_code == 200
    assert "Run vCenter Connector" in response.text
    assert 'action="/ui/connectors/vcenter/run"' in response.text
    assert 'name="mode"' in response.text
    assert "Execution log" not in response.text


def test_connectors_prometheus_tab_renders_connector_form(client) -> None:
    response = client.get("/ui/connectors?tab=prometheus")

    assert response.status_code == 200
    assert "Run Prometheus Connector" in response.text
    assert 'action="/ui/connectors/prometheus/run"' in response.text
    assert 'name="query"' in response.text
    assert 'name="ip_label"' in response.text
    assert "Execution log" not in response.text


def test_connectors_elasticsearch_tab_renders_connector_form(client) -> None:
    response = client.get("/ui/connectors?tab=elasticsearch")

    assert response.status_code == 200
    assert "Run Elasticsearch Connector" in response.text
    assert 'action="/ui/connectors/elasticsearch/run"' in response.text
    assert 'name="elasticsearch_url"' in response.text
    assert 'name="api_key"' in response.text
    assert 'class="checkbox-field field-span"' in response.text
    assert 'name="include_cluster_name_tag"' in response.text
    assert "--include-cluster-name-tag" in response.text
    assert "Execution log" not in response.text


def test_connectors_cassandra_tab_renders_connector_form(client) -> None:
    response = client.get("/ui/connectors?tab=cassandra")

    assert response.status_code == 200
    assert "Run Cassandra Connector" in response.text
    assert 'action="/ui/connectors/cassandra/run"' in response.text
    assert 'name="contact_points"' in response.text
    assert 'name="use_tls"' in response.text
    assert 'class="checkbox-field field-span"' in response.text
    assert 'name="include_cluster_name_tag"' in response.text
    assert "--include-cluster-name-tag" in response.text
    assert "Execution log" not in response.text


def test_connectors_ceph_tab_renders_connector_form(client) -> None:
    response = client.get("/ui/connectors?tab=ceph")

    assert response.status_code == 200
    assert "Run Ceph Connector" in response.text
    assert 'action="/ui/connectors/ceph/run"' in response.text
    assert 'name="ceph_url"' in response.text
    assert 'name="include_cluster_name_tag"' in response.text
    assert 'name="include_label_tags"' in response.text
    assert "--include-label-tags" in response.text
    assert "Execution log" not in response.text


def test_connectors_kubernetes_tab_renders_connector_form(client) -> None:
    response = client.get("/ui/connectors?tab=kubernetes")

    assert response.status_code == 200
    assert "Run Kubernetes Connector" in response.text
    assert 'action="/ui/connectors/kubernetes/run"' in response.text
    assert 'name="api_url"' in response.text
    assert 'name="token"' in response.text
    assert 'name="include_cluster_name_tag"' in response.text
    assert 'name="include_label_tags"' in response.text
    assert "--include-label-tags" in response.text
    assert "Execution log" not in response.text


def test_connectors_page_auto_polls_when_job_is_running(client, monkeypatch) -> None:
    job_id = "job-running"
    monkeypatch.setattr(
        connectors_routes,
        "_get_connector_job",
        lambda _job_id: (
            {
                "active_tab": "elasticsearch",
                "status": "running",
                "logs": [],
                "toast_messages": [],
                "form_state": connectors_routes._default_elasticsearch_form_state(),
            }
            if _job_id == job_id
            else None
        ),
    )

    response = client.get(f"/ui/connectors?tab=elasticsearch&job_id={job_id}")

    assert response.status_code == 200
    assert "window.location.replace(" in response.text
    assert f"job_id={job_id}" in response.text


def test_connectors_page_stops_polling_after_job_completion(
    client, monkeypatch
) -> None:
    job_id = "job-complete"
    monkeypatch.setattr(
        connectors_routes,
        "_get_connector_job",
        lambda _job_id: (
            {
                "active_tab": "elasticsearch",
                "status": "completed",
                "logs": ["done"],
                "toast_messages": [{"type": "success", "message": "done"}],
                "form_state": connectors_routes._default_elasticsearch_form_state(),
            }
            if _job_id == job_id
            else None
        ),
    )

    response = client.get(f"/ui/connectors?tab=elasticsearch&job_id={job_id}")

    assert response.status_code == 200
    assert "window.location.replace(" not in response.text


def test_vcenter_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "apply",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_vcenter_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_vcenter_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "vCenter dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_vcenter_connector_ui_runs_dry_run_and_shows_logs(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "fetch_vcenter_inventory",
        lambda **_kwargs: (
            [VCenterHostRecord(name="esxi-01.lab", ip_address="10.20.30.40")],
            [
                VCenterVmRecord(
                    name="app-vm-01",
                    ip_address="10.20.30.50",
                    host_name="esxi-01.lab",
                )
            ],
            ["Skipped VM 'no-ip' because no IPv4 guest IP was found."],
        ),
    )
    monkeypatch.setattr(
        connectors_routes,
        "import_vcenter_bundle_via_pipeline",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(would_create=1),
                ip_assets=ImportEntitySummary(
                    would_create=2, would_update=0, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 1 hosts and 1 VMs." in response.text
    assert "Import mode: dry-run." in response.text
    assert "Connector warnings: 1" in response.text
    assert "vCenter dry-run: Connector completed with warnings." in response.text
    assert "toast-warning" in response.text


def test_vcenter_connector_ui_validates_required_fields(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={"server": "", "username": "", "password": "", "mode": "dry-run"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "vCenter server is required." in response.text
    assert "vCenter username is required." in response.text
    assert "vCenter password is required." in response.text


def test_vcenter_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_vcenter_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.VCenterConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "dry-run",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "vCenter connector execution failed." in response.text
    assert "toast-error" in response.text


def test_prometheus_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={
                "prometheus_url": "http://127.0.0.1:9090",
                "query": 'up{job="node"}',
                "ip_label": "instance",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_prometheus_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_prometheus_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={
                "prometheus_url": "http://127.0.0.1:9090",
                "query": 'up{job="node"}',
                "ip_label": "instance",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "Prometheus dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_prometheus_connector_ui_runs_dry_run_and_shows_logs(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_prometheus_connector",
        lambda **_kwargs: (
            ["Collected 2 metric samples.", "Import mode: dry-run."],
            ["Sample 1 skipped: label 'instance' is missing."],
            0,
            0,
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={
                "prometheus_url": "http://127.0.0.1:9090",
                "query": 'up{job="node"}',
                "ip_label": "instance",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 2 metric samples." in response.text
    assert "Import mode: dry-run." in response.text
    assert "Connector warnings: 1" in response.text
    assert "Prometheus dry-run: Connector completed with warnings." in response.text
    assert "toast-warning" in response.text


def test_prometheus_connector_dry_run_logs_ip_preview_and_asset_summary(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        connectors_routes,
        "fetch_prometheus_query_result",
        lambda **_kwargs: [
            PrometheusMetricRecord(labels={"instance": "10.0.0.10:9100"}, value="1"),
            PrometheusMetricRecord(labels={"instance": "10.0.0.11:9100"}, value="1"),
        ],
    )
    monkeypatch.setattr(
        connectors_routes,
        "import_prometheus_bundle_via_pipeline",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(),
                ip_assets=ImportEntitySummary(
                    would_create=1, would_update=1, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )

    logs, warnings, _warning_count, _error_count = (
        connectors_routes._run_prometheus_connector(
            connection=None,
            user=None,
            prometheus_url="http://127.0.0.1:9090",
            query='up{job="node"}',
            ip_label="instance",
            asset_type="OTHER",
            project_name=None,
            tags=None,
            token=None,
            insecure=False,
            timeout=30,
            dry_run=True,
        )
    )

    assert warnings == []
    assert any("Dry-run IP preview (2): 10.0.0.10, 10.0.0.11" in line for line in logs)
    assert any(
        "IP assets summary: create=1, update=1, skip=0." in line for line in logs
    )


def test_prometheus_connector_dry_run_logs_per_ip_change_details(
    monkeypatch, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        legacy_project = repository.create_project(connection, name="Legacy")
        core_project = repository.create_project(connection, name="Core")
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.10",
            asset_type=IPAssetType.VM,
            project_id=legacy_project.id,
            notes="manual note",
            tags=["legacy", "ops"],
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.11",
            asset_type=IPAssetType.OTHER,
            project_id=core_project.id,
            notes="manual keep",
            tags=["monitoring"],
        )

        monkeypatch.setattr(
            connectors_routes,
            "fetch_prometheus_query_result",
            lambda **_kwargs: [
                PrometheusMetricRecord(
                    labels={"instance": "10.0.0.10:9100", "__name__": "up"}, value="1"
                ),
                PrometheusMetricRecord(
                    labels={"instance": "10.0.0.11:9100", "__name__": "up"}, value="1"
                ),
                PrometheusMetricRecord(
                    labels={"instance": "10.0.0.12:9100", "__name__": "up"}, value="1"
                ),
            ],
        )
        monkeypatch.setattr(
            connectors_routes,
            "import_prometheus_bundle_via_pipeline",
            lambda *_args, **_kwargs: ImportApplyResult(
                summary=ImportSummary(
                    vendors=ImportEntitySummary(),
                    projects=ImportEntitySummary(),
                    hosts=ImportEntitySummary(),
                    ip_assets=ImportEntitySummary(
                        would_create=1, would_update=1, would_skip=1
                    ),
                ),
                errors=[],
                warnings=[],
            ),
        )

        logs, warnings, _warning_count, _error_count = (
            connectors_routes._run_prometheus_connector(
                connection=connection,
                user=None,
                prometheus_url="http://127.0.0.1:9090",
                query='up{job="node"}',
                ip_label="instance",
                asset_type="OTHER",
                project_name="Core",
                tags=["monitoring"],
                token=None,
                insecure=False,
                timeout=30,
                dry_run=True,
            )
        )
    finally:
        connection.close()

    assert warnings == []
    assert "Dry-run per-IP change details:" in logs
    assert any(
        "[UPDATE] 10.0.0.10: project Legacy -> Core; "
        "tags +[monitoring] -[legacy, ops]; notes preserved (existing note kept)."
        in line
        for line in logs
    )
    assert any("[SKIP] 10.0.0.11: no field changes." in line for line in logs)
    assert any(
        "[CREATE] 10.0.0.12: type=OTHER; project=Core; host=Unassigned; "
        "tags=[monitoring]; notes=set; archived=false." in line
        for line in logs
    )


def test_prometheus_connector_ui_validates_required_fields(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={"prometheus_url": "", "query": "", "ip_label": "", "mode": "dry-run"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Prometheus URL is required." in response.text
    assert "PromQL query is required." in response.text
    assert "IP label is required." in response.text


def test_prometheus_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_prometheus_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.PrometheusConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={
                "prometheus_url": "http://127.0.0.1:9090",
                "query": 'up{job="node"}',
                "ip_label": "instance",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Prometheus connector execution failed." in response.text
    assert "toast-error" in response.text


def test_elasticsearch_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "api_key": "abc123:def456",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_elasticsearch_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_elasticsearch_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "api_key": "abc123:def456",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "Elasticsearch dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_elasticsearch_connector_passes_cluster_name_tag_option(
    client, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )

    def _fake_run_elasticsearch_connector(**kwargs):
        captured.update(kwargs)
        return (["Import mode: dry-run."], [], 0, 0)

    monkeypatch.setattr(
        connectors_routes,
        "_run_elasticsearch_connector",
        _fake_run_elasticsearch_connector,
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert captured["include_cluster_name_tag"] is True


def test_elasticsearch_connector_validation_preserves_cluster_name_tag_checkbox(
    client,
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            data={
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Elasticsearch URL is required." in response.text
    assert 'name="include_cluster_name_tag" value="1" checked' in response.text


def test_elasticsearch_connector_ui_authentication_is_optional(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_elasticsearch_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "Elasticsearch dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_elasticsearch_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_elasticsearch_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.ElasticsearchConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "api_key": "abc123:def456",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Elasticsearch connector execution failed." in response.text
    assert "toast-error" in response.text


def test_cassandra_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.0.0.10",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_cassandra_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_cassandra_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.0.0.10",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "Cassandra dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_cassandra_connector_passes_cluster_name_tag_option(
    client, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )

    def _fake_run_cassandra_connector(**kwargs):
        captured.update(kwargs)
        return (["Import mode: dry-run."], [], 0, 0)

    monkeypatch.setattr(
        connectors_routes,
        "_run_cassandra_connector",
        _fake_run_cassandra_connector,
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.0.0.10,10.0.0.11",
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
                "use_tls": "1",
                "insecure": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert captured["contact_points"] == ["10.0.0.10", "10.0.0.11"]
    assert captured["include_cluster_name_tag"] is True
    assert captured["use_tls"] is True
    assert captured["insecure"] is True


def test_cassandra_connector_validation_preserves_cluster_name_tag_checkbox(
    client,
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            data={
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "At least one Cassandra contact point is required." in response.text
    assert 'name="include_cluster_name_tag" value="1" checked' in response.text


def test_cassandra_connector_ui_validates_port_timeout_and_auth(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.0.0.10",
                "port": "0",
                "username": "cassandra",
                "timeout": "0",
                "insecure": "1",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Port must be a valid number between 1 and 65535." in response.text
    assert "Password is required when username is provided." in response.text
    assert "Insecure TLS requires TLS to be enabled." in response.text
    assert "Timeout must be a positive integer." in response.text


def test_cassandra_connector_ui_runs_dry_run_and_shows_logs(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "fetch_cassandra_nodes",
        lambda **_kwargs: [
            CassandraNodeRecord(
                address="10.20.30.40",
                host_id="node-a",
                cluster_name="Prod.Cassandra 01",
            )
        ],
    )
    monkeypatch.setattr(
        connectors_routes,
        "import_cassandra_bundle_via_pipeline",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(),
                ip_assets=ImportEntitySummary(
                    would_create=1, would_update=0, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.20.30.10",
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 1 nodes from Cassandra metadata." in response.text
    assert "Prepared 1 IP assets from node metadata." in response.text
    assert "Import mode: dry-run." in response.text
    assert "Cassandra dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_cassandra_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_cassandra_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.CassandraConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/cassandra/run",
            follow_redirects=True,
            data={
                "contact_points": "10.0.0.10",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Cassandra connector execution failed." in response.text
    assert "toast-error" in response.text


def test_ceph_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text


def test_ceph_connector_dry_run_allows_non_editor(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_ceph_connector",
        lambda **_kwargs: (["Import mode: dry-run."], [], 0, 0),
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Import mode: dry-run." in response.text
    assert "Ceph dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_ceph_connector_passes_tag_options(client, monkeypatch) -> None:
    captured: dict[str, object] = {}

    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )

    def _fake_run_ceph_connector(**kwargs):
        captured.update(kwargs)
        return (["Import mode: dry-run."], [], 0, 0)

    monkeypatch.setattr(
        connectors_routes, "_run_ceph_connector", _fake_run_ceph_connector
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "dry-run",
                "insecure": "1",
                "include_cluster_name_tag": "1",
                "include_label_tags": "1",
                "tags": "ceph,nodes",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert captured["ceph_url"] == "https://ceph.example.local:8443"
    assert captured["username"] == "admin"
    assert captured["password"] == "secret"
    assert captured["insecure"] is True
    assert captured["include_cluster_name_tag"] is True
    assert captured["include_label_tags"] is True
    assert captured["tags"] == ["ceph", "nodes"]


def test_ceph_connector_validation_preserves_checkboxes(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            data={
                "mode": "dry-run",
                "include_cluster_name_tag": "1",
                "include_label_tags": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Ceph Dashboard URL is required." in response.text
    assert "Ceph username is required." in response.text
    assert "Ceph password is required." in response.text
    assert 'name="include_cluster_name_tag" value="1" checked' in response.text
    assert 'name="include_label_tags" value="1" checked' in response.text


def test_ceph_connector_ui_validates_timeout(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "timeout": "0",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Timeout must be a positive integer." in response.text


def test_ceph_connector_ui_runs_dry_run_and_shows_logs(client, monkeypatch) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "fetch_ceph_hosts",
        lambda **_kwargs: [
            CephHostRecord(
                hostname="ceph-a",
                addr="10.20.30.40",
                labels=("mon",),
                status="online",
            )
        ],
    )
    monkeypatch.setattr(
        connectors_routes,
        "import_ceph_bundle_via_pipeline",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(would_create=1, would_update=0, would_skip=0),
                ip_assets=ImportEntitySummary(
                    would_create=1, would_update=0, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "dry-run",
                "include_label_tags": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 1 hosts from Ceph Dashboard." in response.text
    assert "Prepared 1 hosts and 1 IP assets from Ceph host inventory." in response.text
    assert "Import mode: dry-run." in response.text
    assert "Ceph dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text


def test_ceph_connector_failure_uses_toast_without_inline_error(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_ceph_connector",
        lambda **_kwargs: (_ for _ in ()).throw(
            connectors_routes.CephConnectorError("boom")
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Ceph connector execution failed." in response.text
    assert "toast-error" in response.text


def test_vcenter_connector_apply_writes_import_run_audit_log(
    client, monkeypatch
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-editor-vcenter",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_vcenter_inventory",
        lambda **_kwargs: (
            [VCenterHostRecord(name="esxi-02.lab", ip_address="10.40.1.10")],
            [],
            [],
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/vcenter/run",
            follow_redirects=True,
            data={
                "server": "vc.example.local",
                "username": "administrator@vsphere.local",
                "password": "secret",
                "mode": "apply",
                "port": "443",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = []
        for _ in range(20):
            logs = repository.list_audit_logs(
                connection, target_type="IMPORT_RUN", limit=10
            )
            if logs:
                break
            time.sleep(0.05)
        assert any(log.target_label == "connector_vcenter" for log in logs)
    finally:
        connection.close()


def test_prometheus_connector_dry_run_does_not_write_import_run_audit_log(
    client,
    monkeypatch,
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-viewer-prom",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_prometheus_query_result",
        lambda **_kwargs: [
            PrometheusMetricRecord(labels={"instance": "10.20.0.10:9100"}, value="1")
        ],
    )
    try:
        response = client.post(
            "/ui/connectors/prometheus/run",
            follow_redirects=True,
            data={
                "prometheus_url": "http://127.0.0.1:9090",
                "query": 'up{job="node"}',
                "ip_label": "instance",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = repository.list_audit_logs(
            connection, target_type="IMPORT_RUN", limit=10
        )
        assert logs == []
    finally:
        connection.close()


def test_elasticsearch_connector_apply_writes_import_run_audit_log(
    client, monkeypatch
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-editor-es",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_elasticsearch_nodes",
        lambda **_kwargs: [
            ElasticsearchNodeRecord(
                node_id="node-1",
                name="es-1",
                http_publish_address="10.50.0.10:9200",
                transport_publish_address=None,
                ip=None,
                host=None,
            )
        ],
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "api_key": "abc123:def456",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = []
        for _ in range(20):
            logs = repository.list_audit_logs(
                connection, target_type="IMPORT_RUN", limit=10
            )
            if logs:
                break
            time.sleep(0.05)
        assert any(log.target_label == "connector_elasticsearch" for log in logs)
    finally:
        connection.close()


def test_elasticsearch_connector_dry_run_does_not_write_import_run_audit_log(
    client, monkeypatch
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-viewer-es",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_elasticsearch_nodes",
        lambda **_kwargs: [
            ElasticsearchNodeRecord(
                node_id="node-1",
                name="es-1",
                http_publish_address="10.50.0.11:9200",
                transport_publish_address=None,
                ip=None,
                host=None,
            )
        ],
    )
    try:
        response = client.post(
            "/ui/connectors/elasticsearch/run",
            follow_redirects=True,
            data={
                "elasticsearch_url": "https://127.0.0.1:9200",
                "api_key": "abc123:def456",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = repository.list_audit_logs(
            connection, target_type="IMPORT_RUN", limit=10
        )
        assert logs == []
    finally:
        connection.close()


def test_ceph_connector_apply_writes_import_run_audit_log(client, monkeypatch) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-editor-ceph",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_ceph_hosts",
        lambda **_kwargs: [CephHostRecord(hostname="ceph-a", addr="10.60.0.10")],
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = []
        for _ in range(20):
            logs = repository.list_audit_logs(
                connection, target_type="IMPORT_RUN", limit=10
            )
            if logs:
                break
            time.sleep(0.05)
        assert any(log.target_label == "connector_ceph" for log in logs)
    finally:
        connection.close()


def test_ceph_connector_dry_run_does_not_write_import_run_audit_log(
    client, monkeypatch
) -> None:
    import os

    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        db.init_db(connection)
        actor = repository.create_user(
            connection,
            username="connector-viewer-ceph",
            hashed_password="x",
            role=UserRole.VIEWER,
        )
    finally:
        connection.close()

    app.dependency_overrides[ui.get_current_ui_user] = lambda: actor
    monkeypatch.setattr(
        connectors_routes,
        "fetch_ceph_hosts",
        lambda **_kwargs: [CephHostRecord(hostname="ceph-a", addr="10.60.0.11")],
    )
    try:
        response = client.post(
            "/ui/connectors/ceph/run",
            follow_redirects=True,
            data={
                "ceph_url": "https://ceph.example.local:8443",
                "username": "admin",
                "password": "secret",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        logs = repository.list_audit_logs(
            connection, target_type="IMPORT_RUN", limit=10
        )
        assert logs == []
    finally:
        connection.close()


def test_kubernetes_connector_apply_mode_requires_editor_role(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )
    try:
        response = client.post(
            "/ui/connectors/kubernetes/run",
            follow_redirects=True,
            data={
                "api_url": "https://k8s.example.local:6443",
                "token": "secret-token",
                "mode": "apply",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
    assert "Apply mode is restricted to editor accounts." in response.text
    assert "toast-error" in response.text
    assert "secret-token" not in response.text


def test_kubernetes_connector_ui_validates_required_fields(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    try:
        response = client.post(
            "/ui/connectors/kubernetes/run",
            follow_redirects=True,
            data={"api_url": "", "token": "", "mode": "dry-run"},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 400
    assert "Kubernetes API URL is required." in response.text
    assert "Kubernetes bearer token is required." in response.text


def test_kubernetes_connector_ui_runs_dry_run_and_redacts_token(
    client, monkeypatch
) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        2, "editor", "x", UserRole.EDITOR, True
    )
    monkeypatch.setattr(
        connectors_routes,
        "_run_kubernetes_connector",
        lambda **_kwargs: (
            [
                "Collected 1 nodes from Kubernetes.",
                "Prepared 1 hosts and 1 IP assets from Kubernetes node inventory.",
                "Import mode: dry-run.",
            ],
            [],
            0,
            0,
        ),
    )
    try:
        response = client.post(
            "/ui/connectors/kubernetes/run",
            follow_redirects=True,
            data={
                "api_url": "https://k8s.example.local:6443",
                "token": "secret-token",
                "mode": "dry-run",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert "Execution log" in response.text
    assert "Collected 1 nodes from Kubernetes." in response.text
    assert "Kubernetes dry-run: Connector completed successfully." in response.text
    assert "toast-success" in response.text
    assert "secret-token" not in response.text


def test_kubernetes_connector_passes_label_and_cluster_tag_options(
    client, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        10, "viewer", "x", UserRole.VIEWER, True
    )

    def _fake_run_kubernetes_connector(**kwargs):
        captured.update(kwargs)
        return (["Import mode: dry-run."], [], 0, 0)

    monkeypatch.setattr(
        connectors_routes,
        "_run_kubernetes_connector",
        _fake_run_kubernetes_connector,
    )
    try:
        response = client.post(
            "/ui/connectors/kubernetes/run",
            follow_redirects=True,
            data={
                "api_url": "https://k8s.example.local:6443",
                "token": "secret-token",
                "mode": "dry-run",
                "cluster_name": "Prod Cluster",
                "include_cluster_name_tag": "1",
                "include_label_tags": "1",
            },
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    response = _resolve_connector_response(client, response)
    assert response.status_code == 200
    assert captured["cluster_name"] == "Prod Cluster"
    assert captured["include_cluster_name_tag"] is True
    assert captured["include_label_tags"] is True
    assert captured["token"] == "secret-token"
    assert "secret-token" not in response.text


def test_kubernetes_connector_dry_run_logs_ip_preview_and_summaries(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        connectors_routes,
        "fetch_kubernetes_nodes",
        lambda **_kwargs: [
            KubernetesNodeRecord(name="worker-a", internal_ips=("10.70.0.10",)),
            KubernetesNodeRecord(name="worker-b", internal_ips=("10.70.0.11",)),
        ],
    )
    monkeypatch.setattr(
        connectors_routes,
        "import_kubernetes_bundle_via_pipeline",
        lambda *_args, **_kwargs: ImportApplyResult(
            summary=ImportSummary(
                vendors=ImportEntitySummary(),
                projects=ImportEntitySummary(),
                hosts=ImportEntitySummary(would_create=2),
                ip_assets=ImportEntitySummary(
                    would_create=1, would_update=1, would_skip=0
                ),
            ),
            errors=[],
            warnings=[],
        ),
    )

    logs, warnings, _warning_count, _error_count = (
        connectors_routes._run_kubernetes_connector(
            connection=None,
            user=None,
            api_url="https://k8s.example.local:6443",
            token="secret-token",
            insecure=False,
            asset_type="OS",
            project_name=None,
            tags=None,
            note=None,
            cluster_name=None,
            include_cluster_name_tag=False,
            include_label_tags=False,
            timeout=30,
            dry_run=True,
        )
    )

    assert warnings == []
    assert any(
        "Dry-run IP preview (2): 10.70.0.10, 10.70.0.11" in line for line in logs
    )
    assert any("Hosts summary: create=2, update=0, skip=0." in line for line in logs)
    assert any(
        "IP assets summary: create=1, update=1, skip=0." in line for line in logs
    )
