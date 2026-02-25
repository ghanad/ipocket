from __future__ import annotations

import json
import ssl

from app.connectors import elasticsearch
from app.connectors.elasticsearch import (
    ElasticsearchNodeRecord,
    build_import_bundle_from_elasticsearch,
    extract_ip_assets_from_nodes,
    fetch_elasticsearch_nodes,
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


def test_fetch_elasticsearch_nodes_parses_nodes_payload(monkeypatch) -> None:
    payload = json.dumps(
        {
            "nodes": {
                "node-a": {
                    "name": "es-a",
                    "http": {"publish_address": "10.10.0.1:9200"},
                    "transport": {"publish_address": "10.10.0.1:9300"},
                    "ip": "10.10.0.1",
                    "host": "es-a.local",
                }
            }
        }
    ).encode("utf-8")

    def _fake_urlopen(request, timeout, context):
        assert request.full_url == "https://es.example.local/_nodes/http,transport"
        assert timeout == 30
        assert isinstance(context, ssl.SSLContext)
        return _FakeResponse(payload)

    monkeypatch.setattr(elasticsearch.urllib_request, "urlopen", _fake_urlopen)

    result = fetch_elasticsearch_nodes(elasticsearch_url="https://es.example.local")

    assert result == [
        ElasticsearchNodeRecord(
            node_id="node-a",
            name="es-a",
            http_publish_address="10.10.0.1:9200",
            transport_publish_address="10.10.0.1:9300",
            ip="10.10.0.1",
            host="es-a.local",
        )
    ]


def test_fetch_elasticsearch_nodes_uses_basic_auth(monkeypatch) -> None:
    payload = b'{"nodes":{}}'
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout, context):
        captured["auth"] = dict(request.header_items()).get("Authorization")
        captured["context"] = context
        return _FakeResponse(payload)

    monkeypatch.setattr(elasticsearch.urllib_request, "urlopen", _fake_urlopen)
    fetch_elasticsearch_nodes(
        elasticsearch_url="https://es.example.local",
        username="elastic",
        password="secret",
    )

    assert captured["auth"] == "Basic ZWxhc3RpYzpzZWNyZXQ="
    assert isinstance(captured["context"], ssl.SSLContext)


def test_fetch_elasticsearch_nodes_uses_api_key_id_key(monkeypatch) -> None:
    payload = b'{"nodes":{}}'
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout, context):
        captured["auth"] = dict(request.header_items()).get("Authorization")
        return _FakeResponse(payload)

    monkeypatch.setattr(elasticsearch.urllib_request, "urlopen", _fake_urlopen)
    fetch_elasticsearch_nodes(
        elasticsearch_url="https://es.example.local",
        api_key="abc123:def456",
    )

    assert captured["auth"] == "ApiKey YWJjMTIzOmRlZjQ1Ng=="


def test_fetch_elasticsearch_nodes_uses_api_key_base64_as_is(monkeypatch) -> None:
    payload = b'{"nodes":{}}'
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout, context):
        captured["auth"] = dict(request.header_items()).get("Authorization")
        return _FakeResponse(payload)

    monkeypatch.setattr(elasticsearch.urllib_request, "urlopen", _fake_urlopen)
    fetch_elasticsearch_nodes(
        elasticsearch_url="https://es.example.local",
        api_key="QVBJS2V5QmFzZTY0",
    )

    assert captured["auth"] == "ApiKey QVBJS2V5QmFzZTY0"


def test_extract_ip_assets_from_nodes_deduplicates_and_warns() -> None:
    records = [
        ElasticsearchNodeRecord(
            node_id="a",
            name="es-a",
            http_publish_address="10.0.0.1:9200",
            transport_publish_address=None,
            ip=None,
            host=None,
        ),
        ElasticsearchNodeRecord(
            node_id="b",
            name="es-b",
            http_publish_address=None,
            transport_publish_address="10.0.0.1:9300",
            ip=None,
            host=None,
        ),
        ElasticsearchNodeRecord(
            node_id="c",
            name="es-c",
            http_publish_address=None,
            transport_publish_address=None,
            ip="2001:db8::1",
            host=None,
        ),
        ElasticsearchNodeRecord(
            node_id="d",
            name="es-d",
            http_publish_address="127.0.0.1:9200",
            transport_publish_address=None,
            ip=None,
            host=None,
        ),
        ElasticsearchNodeRecord(
            node_id="e",
            name="es-e",
            http_publish_address=None,
            transport_publish_address=None,
            ip=None,
            host="bad-host",
        ),
        ElasticsearchNodeRecord(
            node_id="f",
            name="es-f",
            http_publish_address=None,
            transport_publish_address=None,
            ip=None,
            host=None,
        ),
    ]

    ip_assets, warnings = extract_ip_assets_from_nodes(
        records,
        default_type="OS",
        project_name="Core",
        tags=["elasticsearch", "cluster"],
        note="Imported from Elasticsearch nodes",
    )

    assert len(ip_assets) == 1
    assert ip_assets[0]["ip_address"] == "10.0.0.1"
    assert ip_assets[0]["type"] == "OS"
    assert ip_assets[0]["project_name"] == "Core"
    assert ip_assets[0]["tags"] == ["elasticsearch", "cluster"]
    assert ip_assets[0]["merge_tags"] is True
    assert ip_assets[0]["notes"] == "Imported from Elasticsearch nodes"
    assert ip_assets[0]["notes_provided"] is True

    assert len(warnings) == 5
    assert "Duplicate IP '10.0.0.1'" in warnings[0]
    assert "IPv6" in warnings[1]
    assert "loopback IP '127.0.0.1'" in warnings[2]
    assert "does not contain a valid IPv4 address" in warnings[3]
    assert "no IP candidate found" in warnings[4]


def test_extract_ip_assets_from_nodes_omits_notes_when_not_provided() -> None:
    records = [
        ElasticsearchNodeRecord(
            node_id="a",
            name="es-a",
            http_publish_address=None,
            transport_publish_address=None,
            ip="10.0.0.5",
            host=None,
        )
    ]
    ip_assets, warnings = extract_ip_assets_from_nodes(records, default_type="OTHER")

    assert warnings == []
    assert "notes" not in ip_assets[0]
    assert "notes_provided" not in ip_assets[0]


def test_build_import_bundle_from_elasticsearch_builds_schema_v1() -> None:
    ip_assets = [
        {
            "ip_address": "10.20.30.40",
            "type": "OTHER",
            "merge_tags": True,
            "archived": False,
        }
    ]

    bundle, warnings = build_import_bundle_from_elasticsearch(
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

    monkeypatch.setattr(elasticsearch, "run_import", _fake_run_import)

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
    assert captured["audit_source"] == "connector_elasticsearch"
    assert captured["audit_mode"] == "dry-run"
    assert captured["audit_input_label"] == "connector:elasticsearch"
    assert captured["audit_user"] == "alice"
    assert json.loads(captured["inputs"]["bundle"].decode("utf-8")) == {
        "app": "ipocket",
        "schema_version": "1",
        "data": {},
    }
