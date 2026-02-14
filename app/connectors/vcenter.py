from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import ssl
from typing import Any, Optional, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request


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
                "preserve_existing_notes": True,
                "merge_tags": True,
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
                "preserve_existing_notes": True,
                "merge_tags": True,
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
    service_instance: Any,
    vim: Any,
) -> tuple[list[VCenterHostRecord], list[VCenterVmRecord], list[str]]:
    content = service_instance.RetrieveContent()
    view_manager = content.viewManager

    host_view = view_manager.CreateContainerView(
        content.rootFolder,
        [vim.HostSystem],
        True,
    )
    try:
        host_systems = list(host_view.view)
    finally:
        host_view.Destroy()

    vm_view = view_manager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True,
    )
    try:
        vms = list(vm_view.view)
    finally:
        vm_view.Destroy()

    hosts, host_warnings = parse_host_systems(host_systems)
    vm_records, vm_warnings = parse_virtual_machines(vms)
    return hosts, vm_records, [*host_warnings, *vm_warnings]


def fetch_vcenter_inventory(
    *,
    server: str,
    username: str,
    password: str,
    port: int = 443,
    insecure: bool = False,
) -> tuple[list[VCenterHostRecord], list[VCenterVmRecord], list[str]]:
    try:
        from pyVim.connect import Disconnect, SmartConnect
        from pyVmomi import vim
    except ImportError as exc:
        raise VCenterConnectorError(
            "Missing dependency 'pyvmomi'. Install it with: pip install -r requirements.txt"
        ) from exc

    ssl_context = ssl._create_unverified_context() if insecure else None
    try:
        service_instance = SmartConnect(
            host=server,
            user=username,
            pwd=password,
            port=port,
            sslContext=ssl_context,
        )
    except Exception as exc:  # pragma: no cover
        raise VCenterConnectorError(
            f"Failed to connect to vCenter '{server}': {exc}"
        ) from exc

    try:
        return _collect_inventory(service_instance, vim)
    finally:
        Disconnect(service_instance)


def write_bundle_json(bundle: dict[str, object], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(bundle, output_file, indent=2)
        output_file.write("\n")


def _build_import_url(base_url: str, dry_run: bool) -> str:
    normalized = base_url.rstrip("/")
    query = "dry_run=1" if dry_run else "dry_run=0"
    return f"{normalized}/import/bundle?{query}"


def import_bundle_via_api(
    *,
    bundle: dict[str, object],
    ipocket_url: str,
    token: str,
    dry_run: bool,
    insecure: bool = False,
    timeout_seconds: int = 30,
) -> dict[str, object]:
    boundary = "----ipocket-vcenter-boundary"
    bundle_payload = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            b'Content-Disposition: form-data; name="file"; filename="bundle.json"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            bundle_payload,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    request = urllib_request.Request(
        _build_import_url(ipocket_url, dry_run=dry_run),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    ssl_context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout_seconds,
            context=ssl_context,
        ) as response:
            response_payload = response.read()
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise VCenterConnectorError(
            f"ipocket import request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise VCenterConnectorError(
            f"Failed to call ipocket import API: {exc}"
        ) from exc

    try:
        parsed = json.loads(response_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VCenterConnectorError(
            "ipocket import API returned invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise VCenterConnectorError(
            "ipocket import API returned an unexpected payload."
        )
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export vCenter hosts/VMs and optionally import directly into ipocket."
    )
    parser.add_argument("--server", required=True, help="vCenter server hostname or IP")
    parser.add_argument("--username", required=True, help="vCenter username")
    parser.add_argument("--password", required=True, help="vCenter password")
    parser.add_argument(
        "--mode",
        choices=("file", "dry-run", "apply"),
        default="file",
        help="file=write bundle only, dry-run/apply=call ipocket import API.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Path to save bundle.json (required in file mode).",
    )
    parser.add_argument(
        "--ipocket-url",
        required=False,
        help="ipocket base URL (example: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--token",
        required=False,
        help="Bearer token for ipocket API auth.",
    )
    parser.add_argument(
        "--ipocket-insecure",
        action="store_true",
        help="Disable TLS verification for ipocket API HTTPS calls.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=443,
        help="vCenter port (default: 443)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for vCenter connection.",
    )
    return parser


def _validate_cli_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    if args.mode == "file" and not args.output:
        parser.error("--output is required when --mode=file")
    if args.mode in {"dry-run", "apply"} and not args.ipocket_url:
        parser.error("--ipocket-url is required when --mode is dry-run/apply")
    if args.mode in {"dry-run", "apply"} and not args.token:
        parser.error("--token is required when --mode is dry-run/apply")


def _print_import_result(payload: dict[str, object]) -> None:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        total = summary.get("total")
        if isinstance(total, dict):
            created = int(total.get("would_create", 0))
            updated = int(total.get("would_update", 0))
            skipped = int(total.get("would_skip", 0))
            print(f"Import summary: create={created}, update={updated}, skip={skipped}")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        print("Import errors:")
        for issue in errors:
            if not isinstance(issue, dict):
                continue
            print(f"- {issue.get('location', 'import')}: {issue.get('message', '')}")

    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        print("Import warnings:")
        for issue in warnings:
            if not isinstance(issue, dict):
                continue
            print(f"- {issue.get('location', 'import')}: {issue.get('message', '')}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_cli_args(parser, args)

    try:
        hosts, vms, inventory_warnings = fetch_vcenter_inventory(
            server=args.server,
            username=args.username,
            password=args.password,
            port=args.port,
            insecure=args.insecure,
        )
    except VCenterConnectorError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    bundle, bundle_warnings = build_import_bundle(hosts, vms)
    all_warnings = [*inventory_warnings, *bundle_warnings]

    if args.output:
        write_bundle_json(bundle, args.output)
        print(f"Bundle written to {args.output}")

    print(f"Collected {len(hosts)} hosts and {len(vms)} VMs from vCenter")
    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(f"- {warning}")

    if args.mode in {"dry-run", "apply"}:
        try:
            result = import_bundle_via_api(
                bundle=bundle,
                ipocket_url=args.ipocket_url,
                token=args.token,
                dry_run=args.mode == "dry-run",
                insecure=args.ipocket_insecure,
            )
        except VCenterConnectorError as exc:
            parser.exit(status=1, message=f"error: {exc}\n")

        print(f"ipocket import mode: {args.mode}")
        _print_import_result(result)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
