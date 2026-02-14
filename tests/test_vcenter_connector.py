from __future__ import annotations

from types import SimpleNamespace

from app.connectors import vcenter
from app.connectors.vcenter import (
    VCenterHostRecord,
    VCenterVmRecord,
    _build_import_url,
    build_import_bundle,
    import_bundle_via_api,
    parse_host_systems,
    parse_virtual_machines,
)


def test_parse_host_systems_prefers_first_valid_ipv4() -> None:
    host_with_vnic_ip = SimpleNamespace(
        name="esxi-01.lab",
        summary=SimpleNamespace(managementServerIp="not-an-ip"),
        config=SimpleNamespace(
            network=SimpleNamespace(
                vnic=[
                    SimpleNamespace(
                        spec=SimpleNamespace(
                            ip=SimpleNamespace(ipAddress="10.20.30.40")
                        )
                    )
                ]
            )
        ),
    )
    host_without_ip = SimpleNamespace(name="esxi-02.lab")

    hosts, warnings = parse_host_systems([host_with_vnic_ip, host_without_ip])

    assert hosts == [VCenterHostRecord(name="esxi-01.lab", ip_address="10.20.30.40")]
    assert len(warnings) == 1
    assert "esxi-02.lab" in warnings[0]


def test_parse_virtual_machines_uses_guest_ip_and_runtime_host_name() -> None:
    vm = SimpleNamespace(
        name="app-vm-01",
        guest=SimpleNamespace(
            ipAddress=None,
            net=[SimpleNamespace(ipAddress=["2001:db8::1", "192.168.50.10"])],
        ),
        runtime=SimpleNamespace(host=SimpleNamespace(name="esxi-01.lab")),
    )
    vm_without_ip = SimpleNamespace(
        name="app-vm-02",
        guest=SimpleNamespace(ipAddress="2001:db8::2", net=[]),
    )

    vms, warnings = parse_virtual_machines([vm, vm_without_ip])

    assert vms == [
        VCenterVmRecord(
            name="app-vm-01",
            ip_address="192.168.50.10",
            host_name="esxi-01.lab",
        )
    ]
    assert len(warnings) == 1
    assert "app-vm-02" in warnings[0]


def test_build_import_bundle_sets_os_vm_types_and_esxi_tag() -> None:
    hosts = [VCenterHostRecord(name="esxi-01.lab", ip_address="10.0.0.11")]
    vms = [
        VCenterVmRecord(
            name="app-vm-01",
            ip_address="10.0.1.10",
            host_name="esxi-01.lab",
        )
    ]

    bundle, warnings = build_import_bundle(
        hosts,
        vms,
        exported_at="2024-01-01T00:00:00+00:00",
    )

    assert warnings == []
    assert bundle["schema_version"] == "1"
    assert bundle["exported_at"] == "2024-01-01T00:00:00+00:00"

    hosts_payload = bundle["data"]["hosts"]
    assert hosts_payload == [
        {"name": "esxi-01.lab", "notes": "Imported from vCenter host inventory."}
    ]

    ip_assets_payload = bundle["data"]["ip_assets"]
    assert ip_assets_payload[0]["type"] == "OS"
    assert ip_assets_payload[0]["host_name"] == "esxi-01.lab"
    assert ip_assets_payload[0]["tags"] == ["esxi"]
    assert ip_assets_payload[0]["preserve_existing_notes"] is True
    assert ip_assets_payload[0]["merge_tags"] is True

    assert ip_assets_payload[1]["type"] == "VM"
    assert ip_assets_payload[1]["ip_address"] == "10.0.1.10"
    assert "app-vm-01" in ip_assets_payload[1]["notes"]
    assert ip_assets_payload[1]["preserve_existing_notes"] is True
    assert ip_assets_payload[1]["merge_tags"] is True


def test_build_import_bundle_skips_duplicate_ips() -> None:
    hosts = [VCenterHostRecord(name="esxi-01.lab", ip_address="10.0.0.11")]
    vms = [VCenterVmRecord(name="app-vm-01", ip_address="10.0.0.11")]

    bundle, warnings = build_import_bundle(
        hosts, vms, exported_at="2024-01-01T00:00:00+00:00"
    )

    assert len(bundle["data"]["ip_assets"]) == 1
    assert len(warnings) == 1
    assert "Duplicate IP '10.0.0.11'" in warnings[0]


def test_build_import_url_supports_dry_run_and_apply() -> None:
    assert (
        _build_import_url("http://127.0.0.1:8000/", dry_run=True)
        == "http://127.0.0.1:8000/import/bundle?dry_run=1"
    )
    assert (
        _build_import_url("http://127.0.0.1:8000", dry_run=False)
        == "http://127.0.0.1:8000/import/bundle?dry_run=0"
    )


def test_import_bundle_via_api_posts_multipart_and_parses_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self) -> bytes:
            return (
                b'{"summary":{"total":{"would_create":2,"would_update":0,"would_skip":1}},'
                b'"errors":[],"warnings":[]}'
            )

    def _fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        header_map = dict(request.header_items())
        captured["auth"] = header_map.get("Authorization")
        captured["content_type"] = header_map.get("Content-type")
        captured["body"] = request.data
        return _FakeResponse()

    monkeypatch.setattr(vcenter.urllib_request, "urlopen", _fake_urlopen)

    result = import_bundle_via_api(
        bundle={"app": "ipocket", "schema_version": "1", "data": {}},
        ipocket_url="http://127.0.0.1:8000/",
        token="test-token",
        dry_run=True,
    )

    assert captured["url"] == "http://127.0.0.1:8000/import/bundle?dry_run=1"
    assert captured["timeout"] == 30
    assert captured["auth"] == "Bearer test-token"
    assert "multipart/form-data; boundary=" in str(captured["content_type"])
    body = captured["body"]
    assert isinstance(body, bytes)
    assert b'name="file"; filename="bundle.json"' in body
    assert result["summary"]["total"]["would_create"] == 2
