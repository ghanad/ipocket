from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import db, repository
from app.connectors import cassandra as cassandra_connector
from app.connectors import ceph as ceph_connector
from app.connectors import elasticsearch as elasticsearch_connector
from app.connectors import kubernetes as kubernetes_connector
from app.connectors import prometheus as prometheus_connector
from app.connectors import vcenter as vcenter_connector
from app.connectors.kubernetes import KubernetesNodeRecord
from app.connectors.prometheus import PrometheusMetricRecord
from app.connectors.vcenter import VCenterHostRecord, VCenterVmRecord
from app.imports.models import ImportApplyResult, ImportEntitySummary, ImportSummary
from app.models import IPAssetType, UserRole
from app.routes.ui.connector_routes import kubernetes, prometheus, vcenter
from app.routes.ui.connector_routes.prometheus_preview import _build_prometheus_dry_run_change_logs


CONNECTOR_MODULES = (
    ("vcenter", vcenter_connector),
    ("prometheus", prometheus_connector),
    ("elasticsearch", elasticsearch_connector),
    ("cassandra", cassandra_connector),
    ("ceph", ceph_connector),
    ("kubernetes", kubernetes_connector),
)


def _result(*, hosts=(0, 0, 0), ips=(0, 0, 0)) -> ImportApplyResult:
    return ImportApplyResult(
        summary=ImportSummary(
            vendors=ImportEntitySummary(),
            projects=ImportEntitySummary(),
            hosts=ImportEntitySummary(would_create=hosts[0], would_update=hosts[1], would_skip=hosts[2]),
            ip_assets=ImportEntitySummary(would_create=ips[0], would_update=ips[1], would_skip=ips[2]),
        ),
        errors=[],
        warnings=[],
    )


@pytest.mark.parametrize("connector,module", CONNECTOR_MODULES)
@pytest.mark.parametrize("dry_run,expected_mode", [(True, "dry-run"), (False, "apply")])
def test_connector_imports_preserve_apply_and_dry_run_audit_context(monkeypatch, connector, module, dry_run, expected_mode) -> None:
    captured: dict[str, object] = {}

    def fake_run_import(_connection, _importer, _inputs, *, options=None, dry_run=False, audit_context=None):
        captured.update(dry_run=dry_run, audit_context=audit_context)
        return "ok"

    monkeypatch.setattr(module, "run_import", fake_run_import)
    result = module.import_bundle_via_pipeline(
        "connection",
        bundle={"app": "ipocket", "schema_version": "1", "data": {}},
        user="operator",
        dry_run=dry_run,
    )
    assert result == "ok"
    assert captured["dry_run"] is dry_run
    audit = captured["audit_context"]
    assert audit.source == f"connector_{connector}"
    assert audit.mode == expected_mode
    assert audit.input_label == f"connector:{connector}"


@pytest.mark.parametrize("connector,module", CONNECTOR_MODULES)
@pytest.mark.parametrize("dry_run,expected_audits", [(True, 0), (False, 1)])
def test_connector_apply_writes_import_run_audit_while_dry_run_does_not(tmp_path, connector, module, dry_run, expected_audits) -> None:
    connection = db.connect(str(tmp_path / f"{connector}-{dry_run}.db"))
    try:
        db.init_db(connection)
        actor = repository.create_user(connection, username=f"{connector}-editor", hashed_password="x", role=UserRole.EDITOR)
        result = module.import_bundle_via_pipeline(
            connection,
            bundle={
                "app": "ipocket",
                "schema_version": "1",
                "data": {"vendors": [], "projects": [], "hosts": [], "tags": [], "ip_assets": []},
            },
            user=actor,
            dry_run=dry_run,
        )
        assert result.errors == []
        audits = repository.list_audit_logs(connection, target_type="IMPORT_RUN", limit=10)
        assert len(audits) == expected_audits
        if audits:
            assert audits[0].target_label == f"connector_{connector}"
    finally:
        connection.close()


def test_vcenter_dry_run_invokes_inventory_and_import_flow_with_host_vm_mapping_logs(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        vcenter,
        "fetch_vcenter_inventory",
        lambda **kwargs: (
            [VCenterHostRecord(name="esxi-01", ip_address="10.0.0.10")],
            [VCenterVmRecord(name="vm-01", ip_address="10.0.0.11", host_name="esxi-01")],
            [],
        ),
    )

    def fake_import(_connection, *, bundle, user, dry_run):
        captured.update(bundle=bundle, user=user, dry_run=dry_run)
        return _result(hosts=(1, 0, 0), ips=(2, 0, 0))

    monkeypatch.setattr(vcenter, "import_vcenter_bundle_via_pipeline", fake_import)
    logs, warnings, warning_count, error_count = vcenter._run_vcenter_connector(
        connection="db", user="operator", server="vc.example", username="u", password="p", port=443, insecure=False, dry_run=True
    )
    assert captured["dry_run"] is True
    assets = captured["bundle"]["data"]["ip_assets"]
    assert [(asset["ip_address"], asset["type"]) for asset in assets] == [
        ("10.0.0.10", "OS"),
        ("10.0.0.11", "VM"),
    ]
    assert assets[0]["host_name"] == "esxi-01"
    assert "vm-01" in assets[1]["notes"] and "esxi-01" in assets[1]["notes"]
    assert assets[0]["tags"] == ["esxi"]
    assert "Collected 1 hosts and 1 VMs." in logs
    assert "Prepared bundle with 2 IP assets." in logs
    assert "Import mode: dry-run. Summary create=3, update=0, skip=0." in logs
    assert warnings == [] and warning_count == 0 and error_count == 0


def test_prometheus_dry_run_keeps_ip_preview_summary_and_query_mapping(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return [
            PrometheusMetricRecord(labels={"address": "10.1.0.10:9100"}, value="1"),
            PrometheusMetricRecord(labels={"address": "10.1.0.11:9100"}, value="1"),
        ]

    monkeypatch.setattr(prometheus, "fetch_prometheus_query_result", fake_fetch)
    monkeypatch.setattr(prometheus, "_build_prometheus_dry_run_change_logs", lambda *_args, **_kwargs: ["- [CREATE] 10.1.0.10", "- [UPDATE] 10.1.0.11", "- [SKIP] 10.1.0.12"])
    monkeypatch.setattr(prometheus, "import_prometheus_bundle_via_pipeline", lambda *_args, **_kwargs: _result(ips=(1, 1, 1)))
    logs, warnings, _, _ = prometheus._run_prometheus_connector(
        connection="db", user=None, prometheus_url="http://prom", query='up{job="node"}', ip_label="address", asset_type="OTHER", project_name=None, tags=None, token="token", insecure=False, timeout=15, dry_run=True
    )
    assert captured["query"] == 'up{job="node"}'
    assert "Dry-run IP preview (2): 10.1.0.10, 10.1.0.11" in logs
    assert "IP assets summary: create=1, update=1, skip=1." in logs
    assert all(detail in logs for detail in ("- [CREATE] 10.1.0.10", "- [UPDATE] 10.1.0.11", "- [SKIP] 10.1.0.12"))
    assert warnings == []


def test_prometheus_per_ip_detail_builder_reports_create_update_and_skip(monkeypatch) -> None:
    existing_update = SimpleNamespace(id=1, project_id=None, host_id=None, asset_type=IPAssetType.OTHER, notes=None, archived=False)
    existing_skip = SimpleNamespace(id=2, project_id=None, host_id=None, asset_type=IPAssetType.OTHER, notes=None, archived=False)
    monkeypatch.setattr("app.routes.ui.connector_routes.prometheus_preview.repository.list_projects", lambda _connection: [])
    monkeypatch.setattr("app.routes.ui.connector_routes.prometheus_preview.repository.list_hosts", lambda _connection: [])
    monkeypatch.setattr("app.routes.ui.connector_routes.prometheus_preview.repository.list_tags_for_ip_assets", lambda _connection, ids: {item: [] for item in ids})
    monkeypatch.setattr(
        "app.routes.ui.connector_routes.prometheus_preview.repository.get_ip_asset_by_ip",
        lambda _connection, ip: {"10.2.0.11": existing_update, "10.2.0.12": existing_skip}.get(ip),
    )
    logs = _build_prometheus_dry_run_change_logs("db", ip_assets=[
        {"ip_address": "10.2.0.10", "type": "OTHER"},
        {"ip_address": "10.2.0.11", "type": "OS"},
        {"ip_address": "10.2.0.12", "type": "OTHER"},
    ])
    assert any("[CREATE] 10.2.0.10" in line for line in logs)
    assert any("[UPDATE] 10.2.0.11" in line and "type OTHER -> OS" in line for line in logs)
    assert any("[SKIP] 10.2.0.12" in line for line in logs)


def test_kubernetes_dry_run_keeps_ip_preview_host_and_asset_summaries(monkeypatch) -> None:
    monkeypatch.setattr(kubernetes, "fetch_kubernetes_nodes", lambda **_kwargs: [
        KubernetesNodeRecord(name="worker-a", internal_ips=("10.3.0.10",)),
        KubernetesNodeRecord(name="worker-b", internal_ips=("10.3.0.11",)),
    ])
    monkeypatch.setattr(kubernetes, "import_kubernetes_bundle_via_pipeline", lambda *_args, **_kwargs: _result(hosts=(2, 0, 0), ips=(1, 1, 0)))
    logs, warnings, _, _ = kubernetes._run_kubernetes_connector(
        connection="db", user=None, api_url="https://k8s", token="token", insecure=False, asset_type="OS", project_name=None, tags=None, note=None, cluster_name="prod", include_cluster_name_tag=True, include_label_tags=True, timeout=30, dry_run=True
    )
    assert "Dry-run IP preview (2): 10.3.0.10, 10.3.0.11" in logs
    assert "Hosts summary: create=2, update=0, skip=0." in logs
    assert "IP assets summary: create=1, update=1, skip=0." in logs
    assert warnings == []
