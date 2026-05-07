from __future__ import annotations

import json
import ssl
import sys
import types

import pytest

from app.connectors import cassandra
from app.connectors.cassandra import (
    CassandraConnectorError,
    CassandraNodeRecord,
    CassandraNodeRecords,
    build_import_bundle_from_cassandra,
    extract_ip_assets_from_nodes,
    fetch_cassandra_nodes,
    import_bundle_via_pipeline,
    parse_contact_points,
)


class _FakeHost:
    def __init__(
        self,
        address: str,
        *,
        datacenter: str | None = None,
        rack: str | None = None,
        host_id: str | None = None,
    ):
        self.address = address
        self.datacenter = datacenter
        self.rack = rack
        self.host_id = host_id


class _FakeMetadata:
    cluster_name = "Prod.Cassandra 01"

    def all_hosts(self):
        return [
            _FakeHost(
                "10.0.0.10",
                datacenter="dc1",
                rack="rack1",
                host_id="node-a",
            )
        ]


class _FakeSession:
    def __init__(self):
        self.shutdown_called = False

    def shutdown(self):
        self.shutdown_called = True


def _install_fake_cassandra_driver(monkeypatch, captured: dict[str, object]) -> None:
    fake_session = _FakeSession()

    class _FakeAuthProvider:
        def __init__(self, *, username, password):
            self.username = username
            self.password = password

    class _FakeCluster:
        def __init__(self, **kwargs):
            captured["cluster_kwargs"] = kwargs
            self.metadata = _FakeMetadata()
            self.shutdown_called = False

        def connect(self):
            captured["connect_called"] = True
            return fake_session

        def shutdown(self):
            self.shutdown_called = True
            captured["cluster_shutdown_called"] = True

    cassandra_module = types.ModuleType("cassandra")
    auth_module = types.ModuleType("cassandra.auth")
    cluster_module = types.ModuleType("cassandra.cluster")
    auth_module.PlainTextAuthProvider = _FakeAuthProvider
    cluster_module.Cluster = _FakeCluster
    monkeypatch.setitem(sys.modules, "cassandra", cassandra_module)
    monkeypatch.setitem(sys.modules, "cassandra.auth", auth_module)
    monkeypatch.setitem(sys.modules, "cassandra.cluster", cluster_module)
    captured["session"] = fake_session


def test_parse_contact_points_trims_deduplicates_and_requires_values() -> None:
    assert parse_contact_points(" 10.0.0.10,10.0.0.11,10.0.0.10 ") == [
        "10.0.0.10",
        "10.0.0.11",
    ]
    assert parse_contact_points([" cassandra-a ", "cassandra-b"]) == [
        "cassandra-a",
        "cassandra-b",
    ]
    with pytest.raises(CassandraConnectorError):
        parse_contact_points(" , ")


def test_fetch_cassandra_nodes_uses_auth_tls_and_metadata(monkeypatch) -> None:
    captured: dict[str, object] = {}
    _install_fake_cassandra_driver(monkeypatch, captured)

    result = fetch_cassandra_nodes(
        contact_points=["10.0.0.10"],
        port=9042,
        username="cassandra",
        password="secret",
        use_tls=True,
        insecure=True,
        timeout=7,
    )

    cluster_kwargs = captured["cluster_kwargs"]
    assert cluster_kwargs["contact_points"] == ["10.0.0.10"]
    assert cluster_kwargs["port"] == 9042
    assert cluster_kwargs["connect_timeout"] == 7
    assert cluster_kwargs["auth_provider"].username == "cassandra"
    assert cluster_kwargs["auth_provider"].password == "secret"
    assert isinstance(cluster_kwargs["ssl_context"], ssl.SSLContext)
    assert cluster_kwargs["ssl_context"].verify_mode == ssl.CERT_NONE
    assert captured["connect_called"] is True
    assert captured["session"].shutdown_called is True
    assert captured["cluster_shutdown_called"] is True
    assert result.cluster_name == "Prod.Cassandra 01"
    assert result == [
        CassandraNodeRecord(
            address="10.0.0.10",
            datacenter="dc1",
            rack="rack1",
            host_id="node-a",
            cluster_name="Prod.Cassandra 01",
        )
    ]


def test_extract_ip_assets_from_nodes_deduplicates_and_warns() -> None:
    records = [
        CassandraNodeRecord(address="10.0.0.1", host_id="a"),
        CassandraNodeRecord(address="10.0.0.1", host_id="b"),
        CassandraNodeRecord(address="2001:db8::1", host_id="c"),
        CassandraNodeRecord(address="127.0.0.1", host_id="d"),
        CassandraNodeRecord(address="bad-host", host_id="e"),
        CassandraNodeRecord(address="", host_id="f"),
    ]

    ip_assets, warnings = extract_ip_assets_from_nodes(
        records,
        default_type="OS",
        project_name="Core",
        tags=["cassandra", "nodes"],
        note="Imported from Cassandra nodes",
    )

    assert len(ip_assets) == 1
    assert ip_assets[0]["ip_address"] == "10.0.0.1"
    assert ip_assets[0]["type"] == "OS"
    assert ip_assets[0]["project_name"] == "Core"
    assert ip_assets[0]["tags"] == ["cassandra", "nodes"]
    assert ip_assets[0]["merge_tags"] is True
    assert ip_assets[0]["notes"] == "Imported from Cassandra nodes"
    assert ip_assets[0]["notes_provided"] is True

    assert len(warnings) == 5
    assert "Duplicate IP '10.0.0.1'" in warnings[0]
    assert "IPv6" in warnings[1]
    assert "loopback IP '127.0.0.1'" in warnings[2]
    assert "does not contain a valid IPv4 address" in warnings[3]
    assert "does not contain a valid IPv4 address" in warnings[4]


def test_extract_ip_assets_from_nodes_adds_normalized_cluster_name_tag() -> None:
    records = CassandraNodeRecords(
        [
            CassandraNodeRecord(
                address="10.0.0.5",
                host_id="a",
                cluster_name="Prod.Cassandra 01",
            ),
            CassandraNodeRecord(
                address="10.0.0.6",
                host_id="b",
                cluster_name="Prod.Cassandra 01",
            ),
        ],
        cluster_name="Prod.Cassandra 01",
    )

    ip_assets, warnings = extract_ip_assets_from_nodes(
        records,
        tags=["cassandra", "prod-cassandra-01"],
        include_cluster_name_tag=True,
    )

    assert warnings == []
    assert [asset["tags"] for asset in ip_assets] == [
        ["cassandra", "prod-cassandra-01"],
        ["cassandra", "prod-cassandra-01"],
    ]


def test_extract_ip_assets_from_nodes_warns_when_cluster_tag_missing() -> None:
    records = [CassandraNodeRecord(address="10.0.0.5", host_id="a")]

    ip_assets, warnings = extract_ip_assets_from_nodes(
        records,
        include_cluster_name_tag=True,
    )

    assert "tags" not in ip_assets[0]
    assert warnings == [
        "Cassandra cluster name tag skipped: cluster_name is missing or empty after normalization."
    ]


def test_build_import_bundle_from_cassandra_builds_schema_v1() -> None:
    ip_assets = [
        {
            "ip_address": "10.20.30.40",
            "type": "OTHER",
            "merge_tags": True,
            "archived": False,
        }
    ]

    bundle, warnings = build_import_bundle_from_cassandra(
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

    monkeypatch.setattr(cassandra, "run_import", _fake_run_import)

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
    assert captured["audit_source"] == "connector_cassandra"
    assert captured["audit_mode"] == "dry-run"
    assert captured["audit_input_label"] == "connector:cassandra"
    assert captured["audit_user"] == "alice"
    assert json.loads(captured["inputs"]["bundle"].decode("utf-8")) == {
        "app": "ipocket",
        "schema_version": "1",
        "data": {},
    }
