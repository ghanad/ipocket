from __future__ import annotations

import json
import ssl

import pytest

from app.connectors import ceph
from app.connectors.ceph import (
    CephConnectorError,
    CephHostRecord,
    CephHostRecords,
    build_import_bundle_from_ceph,
    extract_inventory_from_hosts,
    fetch_ceph_hosts,
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


def test_fetch_ceph_hosts_authenticates_and_parses_host_list(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _fake_urlopen(request, timeout, context):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": request.data,
                "timeout": timeout,
                "context": context,
            }
        )
        if request.full_url.endswith("/api/auth"):
            return _FakeResponse(b'{"token":"jwt-token"}')
        return _FakeResponse(
            json.dumps(
                [
                    {
                        "hostname": "ceph-01",
                        "addr": "10.10.0.1",
                        "labels": ["mon", "storage"],
                        "service_type": "host",
                        "services": [{"type": "mon", "id": "a"}],
                        "status": "online",
                    }
                ]
            ).encode("utf-8")
        )

    monkeypatch.setattr(ceph.urllib_request, "urlopen", _fake_urlopen)

    result = fetch_ceph_hosts(
        ceph_url="https://ceph.example.local:8443",
        username="admin",
        password="secret",
        insecure=True,
        timeout=7,
    )

    assert calls[0]["url"] == "https://ceph.example.local:8443/api/auth"
    assert calls[0]["method"] == "POST"
    assert json.loads(calls[0]["body"].decode("utf-8")) == {
        "username": "admin",
        "password": "secret",
    }
    assert calls[1]["url"] == "https://ceph.example.local:8443/api/host"
    assert calls[1]["method"] == "GET"
    assert calls[1]["headers"]["Authorization"] == "Bearer jwt-token"
    assert calls[1]["timeout"] == 7
    assert isinstance(calls[1]["context"], ssl.SSLContext)
    assert calls[1]["context"].verify_mode == ssl.CERT_NONE
    assert result == [
        CephHostRecord(
            hostname="ceph-01",
            addr="10.10.0.1",
            labels=("mon", "storage"),
            service_type="host",
            services=("mon.a",),
            status="online",
        )
    ]


def test_fetch_ceph_hosts_parses_wrapped_payload_with_cluster_name(monkeypatch) -> None:
    def _fake_urlopen(request, timeout, context):
        if request.full_url.endswith("/api/auth"):
            return _FakeResponse(b'{"token":"jwt-token"}')
        return _FakeResponse(
            json.dumps(
                {
                    "cluster_name": "Prod.Ceph 01",
                    "hosts": [
                        {
                            "hostname": "ceph-01",
                            "addr": "10.10.0.1",
                            "services": ["osd.0"],
                        }
                    ],
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(ceph.urllib_request, "urlopen", _fake_urlopen)

    result = fetch_ceph_hosts(
        ceph_url="https://ceph.example.local",
        username="admin",
        password="secret",
    )

    assert result.cluster_name == "Prod.Ceph 01"
    assert result[0].cluster_name == "Prod.Ceph 01"
    assert result[0].services == ("osd.0",)


def test_fetch_ceph_hosts_requires_auth_token(monkeypatch) -> None:
    def _fake_urlopen(request, timeout, context):
        return _FakeResponse(b"{}")

    monkeypatch.setattr(ceph.urllib_request, "urlopen", _fake_urlopen)

    with pytest.raises(CephConnectorError, match="token"):
        fetch_ceph_hosts(
            ceph_url="https://ceph.example.local",
            username="admin",
            password="secret",
        )


def test_extract_inventory_from_hosts_links_hosts_and_warns() -> None:
    records = [
        CephHostRecord(hostname="ceph-a", addr="10.0.0.1", labels=("mon",)),
        CephHostRecord(hostname="ceph-b", addr="10.0.0.1", labels=("osd",)),
        CephHostRecord(hostname="ceph-c", addr="2001:db8::1"),
        CephHostRecord(hostname="ceph-d", addr="127.0.0.1"),
        CephHostRecord(hostname="ceph-e", addr="bad-host"),
        CephHostRecord(hostname="ceph-f", addr=""),
    ]

    hosts, ip_assets, warnings = extract_inventory_from_hosts(
        records,
        default_type="OS",
        project_name="Storage",
        tags=["ceph"],
        note="Imported from Ceph",
        include_label_tags=True,
    )

    assert hosts == [
        {"name": "ceph-a"},
        {"name": "ceph-b"},
        {"name": "ceph-c"},
        {"name": "ceph-d"},
        {"name": "ceph-e"},
        {"name": "ceph-f"},
    ]
    assert ip_assets == [
        {
            "ip_address": "10.0.0.1",
            "type": "OS",
            "host_name": "ceph-a",
            "merge_tags": True,
            "archived": False,
            "project_name": "Storage",
            "tags": ["ceph", "mon"],
            "notes": "Imported from Ceph",
            "notes_provided": True,
        }
    ]
    assert len(warnings) == 5
    assert "Duplicate IP '10.0.0.1'" in warnings[0]
    assert "IPv6" in warnings[1]
    assert "loopback IP '127.0.0.1'" in warnings[2]
    assert "does not contain a valid IPv4 address" in warnings[3]
    assert "does not contain a valid IPv4 address" in warnings[4]


def test_extract_inventory_from_hosts_adds_cluster_name_tag() -> None:
    records = CephHostRecords(
        [CephHostRecord(hostname="ceph-a", addr="10.0.0.1")],
        cluster_name="Prod.Ceph 01",
    )

    hosts, ip_assets, warnings = extract_inventory_from_hosts(
        records,
        tags=["ceph"],
        include_cluster_name_tag=True,
    )

    assert hosts == [{"name": "ceph-a"}]
    assert warnings == []
    assert ip_assets[0]["tags"] == ["ceph", "prod-ceph-01"]


def test_build_import_bundle_from_ceph_builds_schema_v1() -> None:
    hosts = [{"name": "ceph-a"}]
    ip_assets = [
        {
            "ip_address": "10.20.30.40",
            "type": "OTHER",
            "host_name": "ceph-a",
            "merge_tags": True,
            "archived": False,
        }
    ]

    bundle, warnings = build_import_bundle_from_ceph(
        hosts,
        ip_assets,
        exported_at="2024-01-01T00:00:00+00:00",
    )

    assert warnings == []
    assert bundle["schema_version"] == "1"
    assert bundle["exported_at"] == "2024-01-01T00:00:00+00:00"
    assert bundle["data"]["hosts"] == hosts
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

    monkeypatch.setattr(ceph, "run_import", _fake_run_import)

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
    assert captured["audit_source"] == "connector_ceph"
    assert captured["audit_mode"] == "dry-run"
    assert captured["audit_input_label"] == "connector:ceph"
    assert captured["audit_user"] == "alice"


def test_cli_validation_requires_output_or_db_path() -> None:
    with pytest.raises(SystemExit):
        ceph.main(
            [
                "--ceph-url",
                "https://ceph.example.local",
                "--username",
                "admin",
                "--password",
                "secret",
                "--mode",
                "file",
            ]
        )
    with pytest.raises(SystemExit):
        ceph.main(
            [
                "--ceph-url",
                "https://ceph.example.local",
                "--username",
                "admin",
                "--password",
                "secret",
                "--mode",
                "dry-run",
            ]
        )
    with pytest.raises(SystemExit):
        ceph.main(
            [
                "--ceph-url",
                "https://ceph.example.local",
                "--username",
                "admin",
                "--password",
                "secret",
                "--mode",
                "file",
                "--output",
                "bundle.json",
                "--timeout",
                "0",
            ]
        )
