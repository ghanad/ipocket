from __future__ import annotations

import json
from app.connectors import prometheus
from app.connectors.prometheus import (
    PrometheusConnectorError,
    PrometheusMetricRecord,
    build_import_bundle_from_prometheus,
    extract_ip_assets_from_result,
    fetch_prometheus_query_result,
    import_bundle_via_pipeline,
)


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self) -> bytes:
        return self._payload


def test_fetch_prometheus_query_result_parses_vector_payload(monkeypatch) -> None:
    payload = (
        b'{"status":"success","data":{"resultType":"vector","result":['
        b'{"metric":{"__name__":"up","instance":"10.1.1.5:9100"},"value":[1700000000,"1"]}'
        b"]}}"
    )

    def _fake_urlopen(request, timeout, context):
        assert request.full_url == "http://127.0.0.1:9090/api/v1/query?query=up"
        assert timeout == 30
        return _FakeResponse(payload)

    monkeypatch.setattr(prometheus.urllib_request, "urlopen", _fake_urlopen)

    result = fetch_prometheus_query_result(
        prometheus_url="http://127.0.0.1:9090/",
        query="up",
    )

    assert result == [
        PrometheusMetricRecord(
            labels={"__name__": "up", "instance": "10.1.1.5:9100"},
            value="1",
        )
    ]


def test_fetch_prometheus_query_result_uses_bearer_token_header(monkeypatch) -> None:
    payload = b'{"status":"success","data":{"resultType":"vector","result":[]}}'
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout, context):
        captured["auth"] = dict(request.header_items()).get("Authorization")
        return _FakeResponse(payload)

    monkeypatch.setattr(prometheus.urllib_request, "urlopen", _fake_urlopen)

    fetch_prometheus_query_result(
        prometheus_url="http://127.0.0.1:9090",
        query="up",
        token="abc123",
    )

    assert captured["auth"] == "Bearer abc123"


def test_fetch_prometheus_query_result_uses_basic_auth_for_user_pass(
    monkeypatch,
) -> None:
    payload = b'{"status":"success","data":{"resultType":"vector","result":[]}}'
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout, context):
        captured["auth"] = dict(request.header_items()).get("Authorization")
        return _FakeResponse(payload)

    monkeypatch.setattr(prometheus.urllib_request, "urlopen", _fake_urlopen)

    fetch_prometheus_query_result(
        prometheus_url="http://127.0.0.1:9090",
        query="up",
        token="prom_user:prom_pass",
    )

    assert captured["auth"] == "Basic cHJvbV91c2VyOnByb21fcGFzcw=="


def test_fetch_prometheus_query_result_raises_on_non_success_status(
    monkeypatch,
) -> None:
    payload = b'{"status":"error","errorType":"bad_data","error":"invalid query"}'

    monkeypatch.setattr(
        prometheus.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    try:
        fetch_prometheus_query_result(
            prometheus_url="http://127.0.0.1:9090",
            query="bad",
        )
    except PrometheusConnectorError as exc:
        assert "bad_data" in str(exc)
        assert "invalid query" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected PrometheusConnectorError")


def test_fetch_prometheus_query_result_raises_on_non_vector_type(monkeypatch) -> None:
    payload = b'{"status":"success","data":{"resultType":"matrix","result":[]}}'

    monkeypatch.setattr(
        prometheus.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    try:
        fetch_prometheus_query_result(
            prometheus_url="http://127.0.0.1:9090",
            query="up",
        )
    except PrometheusConnectorError as exc:
        assert "resultType" in str(exc)
        assert "vector" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected PrometheusConnectorError")


def test_extract_ip_assets_from_result_uses_custom_label_and_deduplicates() -> None:
    records = [
        PrometheusMetricRecord(
            labels={
                "__name__": "node_uname_info",
                "exported_instance": "10.0.0.1:9100",
            },
            value="1",
        ),
        PrometheusMetricRecord(
            labels={
                "__name__": "node_uname_info",
                "exported_instance": "10.0.0.1:9100",
            },
            value="1",
        ),
        PrometheusMetricRecord(
            labels={"__name__": "node_uname_info", "exported_instance": "2001:db8::1"},
            value="1",
        ),
        PrometheusMetricRecord(
            labels={
                "__name__": "node_uname_info",
                "exported_instance": "127.0.0.1:9100",
            },
            value="1",
        ),
        PrometheusMetricRecord(labels={"__name__": "node_uname_info"}, value="1"),
    ]

    ip_assets, warnings = extract_ip_assets_from_result(
        records,
        ip_label="exported_instance",
        default_type="OTHER",
        project_name="Core",
        tags=["monitoring", "node-exporter"],
        query='node_uname_info{job="node"}',
    )

    assert len(ip_assets) == 1
    assert ip_assets[0]["ip_address"] == "10.0.0.1"
    assert ip_assets[0]["type"] == "OTHER"
    assert ip_assets[0]["project_name"] == "Core"
    assert ip_assets[0]["tags"] == ["monitoring", "node-exporter"]
    assert ip_assets[0]["archived"] is False
    assert ip_assets[0]["preserve_existing_notes"] is True
    assert ip_assets[0]["preserve_existing_type"] is True
    assert "node_uname_info" in str(ip_assets[0]["notes"])

    assert len(warnings) == 4
    assert "Duplicate IP '10.0.0.1' skipped." in warnings[0]
    assert "does not contain a valid IPv4 address" in warnings[1]
    assert "loopback IP '127.0.0.1' is not allowed" in warnings[2]
    assert "label 'exported_instance' is missing" in warnings[3]


def test_build_import_bundle_from_prometheus_builds_schema_v1() -> None:
    ip_assets = [
        {
            "ip_address": "10.10.10.10",
            "type": "OTHER",
            "notes": "test",
            "archived": False,
        }
    ]

    bundle, warnings = build_import_bundle_from_prometheus(
        ip_assets,
        exported_at="2024-01-01T00:00:00+00:00",
    )

    assert warnings == []
    assert bundle["schema_version"] == "1"
    assert bundle["exported_at"] == "2024-01-01T00:00:00+00:00"
    assert bundle["data"]["hosts"] == []
    assert bundle["data"]["ip_assets"] == ip_assets


def test_import_bundle_via_pipeline_calls_run_import(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_import(
        connection, importer, inputs, *, options=None, dry_run=False, audit_context=None
    ):
        captured["connection"] = connection
        captured["importer_type"] = type(importer).__name__
        captured["inputs"] = inputs
        captured["dry_run"] = dry_run
        captured["audit_source"] = audit_context.source if audit_context else None
        captured["audit_mode"] = audit_context.mode if audit_context else None
        captured["audit_input_label"] = (
            audit_context.input_label if audit_context else None
        )
        captured["audit_user"] = audit_context.user if audit_context else None
        return "ok"

    monkeypatch.setattr(prometheus, "run_import", _fake_run_import)

    result = import_bundle_via_pipeline(
        "db-conn",
        bundle={"app": "ipocket", "schema_version": "1", "data": {}},
        user="alice",
        dry_run=True,
    )

    assert result == "ok"
    assert captured["connection"] == "db-conn"
    assert captured["importer_type"] == "BundleImporter"
    assert captured["dry_run"] is True
    assert captured["audit_source"] == "connector_prometheus"
    assert captured["audit_mode"] == "dry-run"
    assert captured["audit_input_label"] == "connector:prometheus"
    assert captured["audit_user"] == "alice"
    assert json.loads(captured["inputs"]["bundle"].decode("utf-8")) == {
        "app": "ipocket",
        "schema_version": "1",
        "data": {},
    }
