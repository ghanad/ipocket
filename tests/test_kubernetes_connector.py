from __future__ import annotations

import json
import ssl

import pytest

from app.connectors import kubernetes
from app.connectors.kubernetes import (
    KubernetesConnectorError,
    KubernetesNodeRecord,
    KubernetesNodeRecords,
    build_import_bundle_from_kubernetes,
    extract_inventory_from_nodes,
    fetch_kubernetes_nodes,
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


def test_fetch_kubernetes_nodes_calls_api_and_parses_node_list(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _fake_urlopen(request, timeout, context):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "timeout": timeout,
                "context": context,
            }
        )
        return _FakeResponse(
            json.dumps(
                {
                    "cluster_name": "Prod Cluster",
                    "items": [
                        {
                            "metadata": {
                                "name": "worker-01",
                                "labels": {
                                    "node-role.kubernetes.io/worker": "true",
                                    "topology.kubernetes.io/zone": "az-a",
                                },
                            },
                            "status": {
                                "addresses": [
                                    {"type": "Hostname", "address": "worker-01"},
                                    {"type": "ExternalIP", "address": "203.0.113.10"},
                                    {"type": "InternalIP", "address": "10.42.0.10"},
                                ]
                            },
                        }
                    ],
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(kubernetes.urllib_request, "urlopen", _fake_urlopen)

    result = fetch_kubernetes_nodes(
        api_url="https://k8s.example.local:6443/",
        token="token-123",
        insecure=True,
        timeout=9,
    )

    assert calls[0]["url"] == "https://k8s.example.local:6443/api/v1/nodes"
    assert calls[0]["method"] == "GET"
    assert calls[0]["headers"]["Authorization"] == "Bearer token-123"
    assert calls[0]["timeout"] == 9
    assert isinstance(calls[0]["context"], ssl.SSLContext)
    assert calls[0]["context"].verify_mode == ssl.CERT_NONE
    assert result.cluster_name == "Prod Cluster"
    assert result == [
        KubernetesNodeRecord(
            name="worker-01",
            internal_ips=("10.42.0.10",),
            labels={
                "node-role.kubernetes.io/worker": "true",
                "topology.kubernetes.io/zone": "az-a",
            },
            cluster_name="Prod Cluster",
        )
    ]


def test_fetch_kubernetes_nodes_rejects_unexpected_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        kubernetes.urllib_request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(b"{}"),
    )

    with pytest.raises(KubernetesConnectorError, match="items list"):
        fetch_kubernetes_nodes(api_url="https://k8s.example.local", token="token")


def test_extract_inventory_from_nodes_maps_hosts_ips_and_warnings() -> None:
    records = [
        KubernetesNodeRecord(
            name="worker-a",
            internal_ips=("10.0.0.1",),
            labels={"node-role.kubernetes.io/worker": "true"},
        ),
        KubernetesNodeRecord(name="worker-b", internal_ips=("10.0.0.1",)),
        KubernetesNodeRecord(name="worker-c", internal_ips=("2001:db8::1",)),
        KubernetesNodeRecord(name="worker-d", internal_ips=("127.0.0.1",)),
        KubernetesNodeRecord(name="worker-e", internal_ips=("bad-host",)),
        KubernetesNodeRecord(name="worker-f", internal_ips=()),
        KubernetesNodeRecord(name="", internal_ips=("10.0.0.7",)),
    ]

    hosts, ip_assets, warnings = extract_inventory_from_nodes(
        records,
        default_type="OS",
        project_name="Platform",
        tags=["kubernetes"],
        note="Imported from Kubernetes",
        include_label_tags=True,
    )

    assert hosts == [
        {"name": "worker-a"},
        {"name": "worker-b"},
        {"name": "worker-c"},
        {"name": "worker-d"},
        {"name": "worker-e"},
        {"name": "worker-f"},
    ]
    assert ip_assets == [
        {
            "ip_address": "10.0.0.1",
            "type": "OS",
            "host_name": "worker-a",
            "merge_tags": True,
            "archived": False,
            "project_name": "Platform",
            "tags": ["kubernetes", "node-role-kubernetes-io-worker-true"],
            "notes": "Imported from Kubernetes",
            "notes_provided": True,
        }
    ]
    assert len(warnings) == 6
    assert "Duplicate IP '10.0.0.1'" in warnings[0]
    assert "IPv6 is not supported" in warnings[1]
    assert "loopback IP is not allowed" in warnings[2]
    assert "not a valid IPv4 address" in warnings[3]
    assert "no InternalIP address found" in warnings[4]
    assert "name is missing" in warnings[5]


def test_extract_inventory_from_nodes_adds_cluster_name_tag() -> None:
    records = KubernetesNodeRecords(
        [KubernetesNodeRecord(name="worker-a", internal_ips=("10.0.0.1",))],
        cluster_name="Prod.Cluster 01",
    )

    hosts, ip_assets, warnings = extract_inventory_from_nodes(
        records,
        tags=["kubernetes"],
        include_cluster_name_tag=True,
    )

    assert hosts == [{"name": "worker-a"}]
    assert warnings == []
    assert ip_assets[0]["tags"] == ["kubernetes", "prod-cluster-01"]


def test_extract_inventory_from_nodes_uses_explicit_cluster_name_tag() -> None:
    hosts, ip_assets, warnings = extract_inventory_from_nodes(
        [KubernetesNodeRecord(name="worker-a", internal_ips=("10.0.0.1",))],
        tags=["kubernetes"],
        include_cluster_name_tag=True,
        cluster_name="Manual Cluster",
    )

    assert hosts == [{"name": "worker-a"}]
    assert warnings == []
    assert ip_assets[0]["tags"] == ["kubernetes", "manual-cluster"]


def test_build_import_bundle_from_kubernetes_builds_schema_v1() -> None:
    hosts = [{"name": "worker-a"}]
    ip_assets = [
        {
            "ip_address": "10.20.30.40",
            "type": "OS",
            "host_name": "worker-a",
            "merge_tags": True,
            "archived": False,
        }
    ]

    bundle, warnings = build_import_bundle_from_kubernetes(
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

    monkeypatch.setattr(kubernetes, "run_import", _fake_run_import)

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
    assert captured["audit_source"] == "connector_kubernetes"
    assert captured["audit_mode"] == "dry-run"
    assert captured["audit_input_label"] == "connector:kubernetes"
    assert captured["audit_user"] == "alice"


def test_cli_validation_requires_output_or_db_path() -> None:
    with pytest.raises(SystemExit):
        kubernetes.main(
            [
                "--api-url",
                "https://k8s.example.local",
                "--token",
                "secret",
                "--mode",
                "file",
            ]
        )
    with pytest.raises(SystemExit):
        kubernetes.main(
            [
                "--api-url",
                "https://k8s.example.local",
                "--token",
                "secret",
                "--mode",
                "dry-run",
            ]
        )
    with pytest.raises(SystemExit):
        kubernetes.main(
            [
                "--api-url",
                "https://k8s.example.local",
                "--token",
                "secret",
                "--mode",
                "file",
                "--output",
                "bundle.json",
                "--timeout",
                "0",
            ]
        )
