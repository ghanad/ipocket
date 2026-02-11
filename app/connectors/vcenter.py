from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import ssl
from typing import Any, Optional, Sequence


class VCenterConnectorError(Exception):
    pass


@dataclass(frozen=True)
class VCenterHostRecord:
    name: str
    ip_address: str


@dataclass(frozen=True)
class VCenterVmRecord:
    name: str
    ip_address: str
    host_name: Optional[str] = None


def _normalize_ipv4(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def _first_ipv4(candidates: Sequence[object]) -> Optional[str]:
    for candidate in candidates:
        normalized = _normalize_ipv4(candidate)
        if normalized:
            return normalized
    return None


def _extract_host_ip(host: Any) -> Optional[str]:
    candidates: list[object] = [getattr(host, "name", None)]

    summary = getattr(host, "summary", None)
    if summary is not None:
        candidates.append(getattr(summary, "managementServerIp", None))

    config = getattr(host, "config", None)
    network = getattr(config, "network", None) if config is not None else None
    vnics = getattr(network, "vnic", None) if network is not None else None
    if vnics:
        for vnic in vnics:
            spec = getattr(vnic, "spec", None)
            ip_info = getattr(spec, "ip", None) if spec is not None else None
            candidates.append(getattr(ip_info, "ipAddress", None))

    return _first_ipv4(candidates)


def _extract_vm_ip(vm: Any) -> Optional[str]:
    guest = getattr(vm, "guest", None)
    candidates: list[object] = []
    if guest is not None:
        candidates.append(getattr(guest, "ipAddress", None))
        nets = getattr(guest, "net", None)
        if nets:
            for net in nets:
                ip_addresses = getattr(net, "ipAddress", None)
                if ip_addresses:
                    candidates.extend(ip_addresses)
    return _first_ipv4(candidates)


def parse_host_systems(
    host_systems: Sequence[Any],
) -> tuple[list[VCenterHostRecord], list[str]]:
    records: list[VCenterHostRecord] = []
    warnings: list[str] = []

    for host in host_systems:
        name = str(getattr(host, "name", "")).strip()
        if not name:
            warnings.append("Skipped host without a name.")
            continue
        ip_address = _extract_host_ip(host)
        if not ip_address:
            warnings.append(
                f"Skipped host '{name}' because no IPv4 management IP was found."
            )
            continue
        records.append(VCenterHostRecord(name=name, ip_address=ip_address))

    return records, warnings


def parse_virtual_machines(
    vms: Sequence[Any],
) -> tuple[list[VCenterVmRecord], list[str]]:
    records: list[VCenterVmRecord] = []
    warnings: list[str] = []

    for vm in vms:
        name = str(getattr(vm, "name", "")).strip()
        if not name:
            warnings.append("Skipped VM without a name.")
            continue
        ip_address = _extract_vm_ip(vm)
        if not ip_address:
            warnings.append(f"Skipped VM '{name}' because no IPv4 guest IP was found.")
            continue
        runtime = getattr(vm, "runtime", None)
        host = getattr(runtime, "host", None) if runtime is not None else None
        host_name = str(getattr(host, "name", "")).strip() or None
        records.append(
            VCenterVmRecord(name=name, ip_address=ip_address, host_name=host_name)
        )

    return records, warnings


def build_import_bundle(
    hosts: Sequence[VCenterHostRecord],
    vms: Sequence[VCenterVmRecord],
    *,
    exported_at: Optional[str] = None,
) -> tuple[dict[str, object], list[str]]:
    export_timestamp = exported_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    host_entries = [
        {"name": host.name, "notes": "Imported from vCenter host inventory."}
        for host in hosts
    ]
    ip_assets: list[dict[str, object]] = []
    warnings: list[str] = []

    seen_ips: set[str] = set()

    for host in hosts:
        if host.ip_address in seen_ips:
            warnings.append(
                f"Duplicate IP '{host.ip_address}' skipped for host '{host.name}'."
            )
            continue
        seen_ips.add(host.ip_address)
        ip_assets.append(
            {
                "ip_address": host.ip_address,
                "type": "OS",
                "host_name": host.name,
                "tags": ["esxi"],
                "notes": f"vCenter host: {host.name}",
                "archived": False,
            }
        )

    for vm in vms:
        if vm.ip_address in seen_ips:
            warnings.append(
                f"Duplicate IP '{vm.ip_address}' skipped for VM '{vm.name}'."
            )
            continue
        seen_ips.add(vm.ip_address)
        notes = f"vCenter VM: {vm.name}"
        if vm.host_name:
            notes = f"{notes} (host: {vm.host_name})"
        ip_assets.append(
            {
                "ip_address": vm.ip_address,
                "type": "VM",
                "notes": notes,
                "archived": False,
            }
        )

    bundle = {
        "app": "ipocket",
        "schema_version": "1",
        "exported_at": export_timestamp,
        "data": {
            "vendors": [],
            "projects": [],
            "hosts": host_entries,
            "ip_assets": ip_assets,
        },
    }

    return bundle, warnings


def _collect_inventory(
    service_instance: Any, vim: Any
) -> tuple[list[VCenterHostRecord], list[VCenterVmRecord], list[str]]:
    content = service_instance.RetrieveContent()
    view_manager = content.viewManager

    host_view = view_manager.CreateContainerView(
        content.rootFolder, [vim.HostSystem], True
    )
    try:
        host_systems = list(host_view.view)
    finally:
        host_view.Destroy()

    vm_view = view_manager.CreateContainerView(
        content.rootFolder, [vim.VirtualMachine], True
    )
    try:
        vms = list(vm_view.view)
    finally:
        vm_view.Destroy()

    hosts, host_warnings = parse_host_systems(host_systems)
    vm_records, vm_warnings = parse_virtual_machines(vms)
    return hosts, vm_records, [*host_warnings, *vm_warnings]


def export_vcenter_bundle(
    *,
    server: str,
    username: str,
    password: str,
    output_path: str,
    port: int = 443,
    insecure: bool = False,
) -> tuple[int, int, list[str]]:
    try:
        from pyVim.connect import Disconnect, SmartConnect
        from pyVmomi import vim
    except ImportError as exc:
        raise VCenterConnectorError(
            "Missing dependency 'pyvmomi'. Install it with: pip install pyvmomi"
        ) from exc

    ssl_context = None
    if insecure:
        ssl_context = ssl._create_unverified_context()

    try:
        service_instance = SmartConnect(
            host=server,
            user=username,
            pwd=password,
            port=port,
            sslContext=ssl_context,
        )
    except Exception as exc:  # pragma: no cover - depends on external vCenter
        raise VCenterConnectorError(
            f"Failed to connect to vCenter '{server}': {exc}"
        ) from exc

    try:
        hosts, vm_records, parse_warnings = _collect_inventory(service_instance, vim)
    finally:
        Disconnect(service_instance)

    bundle, bundle_warnings = build_import_bundle(hosts, vm_records)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(bundle, output_file, indent=2)
        output_file.write("\n")

    return len(hosts), len(vm_records), [*parse_warnings, *bundle_warnings]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export vCenter hosts/VMs into ipocket bundle.json for manual import."
        )
    )
    parser.add_argument("--server", required=True, help="vCenter server hostname or IP")
    parser.add_argument("--username", required=True, help="vCenter username")
    parser.add_argument("--password", required=True, help="vCenter password")
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for bundle.json (import later from ipocket UI)",
    )
    parser.add_argument(
        "--port", type=int, default=443, help="vCenter port (default: 443)"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification when connecting to vCenter.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        host_count, vm_count, warnings = export_vcenter_bundle(
            server=args.server,
            username=args.username,
            password=args.password,
            output_path=args.output,
            port=args.port,
            insecure=args.insecure,
        )
    except VCenterConnectorError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    print(f"Exported {host_count} hosts and {vm_count} VMs to {args.output}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
