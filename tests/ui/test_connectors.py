from __future__ import annotations

import time

from app import db, repository
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
    assert "Available Connectors" in response.text
    assert "vCenter" in response.text
    assert "Prometheus" in response.text


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
