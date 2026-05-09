from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import re
import ssl
from typing import Optional, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.imports import BundleImporter, ImportAuditContext, run_import
from app.imports.models import ImportApplyResult
from app.models import IPAssetType
from app.utils import split_tag_string


class CephConnectorError(Exception):
    pass


@dataclass(frozen=True)
class CephHostRecord:
    hostname: str
    addr: Optional[str]
    labels: tuple[str, ...] = ()
    service_type: Optional[str] = None
    services: tuple[str, ...] = ()
    status: Optional[str] = None
    cluster_name: Optional[str] = None


class CephHostRecords(list[CephHostRecord]):
    def __init__(
        self,
        records: Sequence[CephHostRecord] = (),
        *,
        cluster_name: Optional[str] = None,
    ):
        super().__init__(records)
        self.cluster_name = cluster_name


_CEPH_ACCEPT_HEADER = "application/vnd.ceph.api.v1.0+json"


def _build_ssl_context(*, insecure: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _api_url(ceph_url: str, path: str) -> str:
    return f"{ceph_url.rstrip('/')}/api/{path.lstrip('/')}"


def _request_json(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    timeout: int,
    context: ssl.SSLContext,
    payload: Optional[dict[str, object]] = None,
) -> object:
    body: bytes | None = None
    request_headers = dict(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib_request.Request(
        url,
        data=body,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout,
            context=context,
        ) as response:
            response_payload = response.read()
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise CephConnectorError(
            f"Ceph API request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise CephConnectorError(f"Failed to call Ceph API: {exc}") from exc

    try:
        return json.loads(response_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CephConnectorError("Ceph API returned invalid JSON.") from exc


def _authenticate_ceph(
    *,
    ceph_url: str,
    username: str,
    password: str,
    timeout: int,
    context: ssl.SSLContext,
) -> str:
    payload = _request_json(
        url=_api_url(ceph_url, "auth"),
        method="POST",
        headers={"Accept": _CEPH_ACCEPT_HEADER},
        timeout=timeout,
        context=context,
        payload={"username": username, "password": password},
    )
    if not isinstance(payload, dict):
        raise CephConnectorError("Ceph auth response was not a JSON object.")
    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise CephConnectorError("Ceph auth response did not include a token.")
    return token.strip()


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    for item in value:
        candidate = str(item).strip()
        if candidate:
            normalized.append(candidate)
    return tuple(normalized)


def _normalize_service_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    services: list[str] = []
    for item in value:
        if isinstance(item, dict):
            service_type = str(item.get("type") or "").strip()
            service_id = str(item.get("id") or "").strip()
            label = ".".join(part for part in (service_type, service_id) if part)
        else:
            label = str(item).strip()
        if label:
            services.append(label)
    return tuple(services)


def _extract_host_payloads(
    payload: object,
) -> tuple[list[dict[str, object]], Optional[str]]:
    cluster_name: Optional[str] = None
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], cluster_name
    if not isinstance(payload, dict):
        raise CephConnectorError("Ceph host response was not a JSON object or list.")

    raw_cluster_name = payload.get("cluster_name") or payload.get("cluster")
    if raw_cluster_name is not None:
        cluster_name = str(raw_cluster_name).strip() or None

    for key in ("hosts", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)], cluster_name
        if isinstance(value, dict):
            nested, nested_cluster_name = _extract_host_payloads(value)
            return nested, cluster_name or nested_cluster_name

    if "hostname" in payload or "addr" in payload:
        return [payload], cluster_name
    raise CephConnectorError("Ceph host response did not include host records.")


def _normalize_cluster_name_tag(cluster_name: Optional[str]) -> Optional[str]:
    if cluster_name is None:
        return None
    normalized = re.sub(r"[^a-z0-9_-]+", "-", cluster_name.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or None


def fetch_ceph_hosts(
    *,
    ceph_url: str,
    username: str,
    password: str,
    insecure: bool = False,
    timeout: int = 30,
) -> CephHostRecords:
    context = _build_ssl_context(insecure=insecure)
    token = _authenticate_ceph(
        ceph_url=ceph_url,
        username=username,
        password=password,
        timeout=timeout,
        context=context,
    )
    payload = _request_json(
        url=_api_url(ceph_url, "host"),
        method="GET",
        headers={
            "Accept": _CEPH_ACCEPT_HEADER,
            "Authorization": f"Bearer {token}",
        },
        timeout=timeout,
        context=context,
    )
    host_payloads, cluster_name = _extract_host_payloads(payload)
    records: list[CephHostRecord] = []
    for index, host_payload in enumerate(host_payloads):
        hostname = str(
            host_payload.get("hostname") or host_payload.get("host") or ""
        ).strip()
        if not hostname:
            hostname = f"ceph-host-{index + 1}"
        raw_addr = host_payload.get("addr")
        addr = str(raw_addr).strip() if raw_addr is not None else None
        service_type = (
            str(host_payload.get("service_type")).strip()
            if host_payload.get("service_type") is not None
            else None
        ) or None
        status = (
            str(host_payload.get("status")).strip()
            if host_payload.get("status") is not None
            else None
        ) or None
        records.append(
            CephHostRecord(
                hostname=hostname,
                addr=addr,
                labels=_normalize_string_list(host_payload.get("labels")),
                service_type=service_type,
                services=_normalize_service_list(host_payload.get("services")),
                status=status,
                cluster_name=cluster_name,
            )
        )
    return CephHostRecords(records, cluster_name=cluster_name)


def _normalize_ipv4(value: object) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def extract_inventory_from_hosts(
    records: Sequence[CephHostRecord],
    *,
    default_type: str = "OTHER",
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
    include_cluster_name_tag: bool = False,
    include_label_tags: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    normalized_type = IPAssetType.normalize(default_type).value
    warnings: list[str] = []
    prepared_tags = [tag.strip() for tag in tags if tag.strip()] if tags else []
    if include_cluster_name_tag:
        cluster_name = getattr(records, "cluster_name", None)
        if cluster_name is None:
            for record in records:
                if record.cluster_name is not None:
                    cluster_name = record.cluster_name
                    break
        cluster_tag = _normalize_cluster_name_tag(cluster_name)
        if cluster_tag is None:
            warnings.append(
                "Ceph cluster name tag skipped: cluster_name is missing or empty after normalization."
            )
        elif cluster_tag not in {tag.strip().lower() for tag in prepared_tags}:
            prepared_tags.append(cluster_tag)

    host_entries: list[dict[str, object]] = []
    ip_assets: list[dict[str, object]] = []
    seen_hosts: set[str] = set()
    seen_ips: set[str] = set()

    for record in records:
        hostname = record.hostname.strip()
        if not hostname:
            warnings.append("Ceph host skipped: hostname is missing.")
            continue
        if hostname not in seen_hosts:
            host_payload: dict[str, object] = {"name": hostname}
            host_entries.append(host_payload)
            seen_hosts.add(hostname)

        normalized_ip = _normalize_ipv4(record.addr)
        if not normalized_ip:
            try:
                parsed_candidate = ipaddress.ip_address(str(record.addr or "").strip())
            except ValueError:
                warnings.append(
                    f"Host '{hostname}' skipped: addr '{record.addr or ''}' does not contain a valid IPv4 address."
                )
            else:
                if parsed_candidate.version == 6:
                    warnings.append(
                        f"Host '{hostname}' skipped: addr '{record.addr}' resolved to IPv6, but only IPv4 is supported."
                    )
                else:
                    warnings.append(
                        f"Host '{hostname}' skipped: addr '{record.addr}' is not a usable IPv4 address."
                    )
            continue

        if ipaddress.ip_address(normalized_ip).is_loopback:
            warnings.append(
                f"Host '{hostname}' skipped: loopback IP '{normalized_ip}' is not allowed."
            )
            continue
        if normalized_ip in seen_ips:
            warnings.append(
                f"Duplicate IP '{normalized_ip}' skipped (host '{hostname}')."
            )
            continue
        seen_ips.add(normalized_ip)

        asset_tags = list(prepared_tags)
        if include_label_tags:
            for label in record.labels:
                normalized_label = _normalize_cluster_name_tag(label)
                if normalized_label and normalized_label not in {
                    tag.strip().lower() for tag in asset_tags
                }:
                    asset_tags.append(normalized_label)

        asset_payload: dict[str, object] = {
            "ip_address": normalized_ip,
            "type": normalized_type,
            "host_name": hostname,
            "merge_tags": True,
            "archived": False,
        }
        if project_name:
            asset_payload["project_name"] = project_name
        if asset_tags:
            asset_payload["tags"] = asset_tags
        if note is not None:
            asset_payload["notes"] = note
            asset_payload["notes_provided"] = True

        ip_assets.append(asset_payload)

    return host_entries, ip_assets, warnings


def build_import_bundle_from_ceph(
    hosts: Sequence[dict[str, object]],
    ip_assets: Sequence[dict[str, object]],
    *,
    exported_at: Optional[str] = None,
) -> tuple[dict[str, object], list[str]]:
    export_timestamp = exported_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    warnings: list[str] = []
    prepared_hosts: list[dict[str, object]] = []
    prepared_assets: list[dict[str, object]] = []
    seen_hosts: set[str] = set()
    seen_ips: set[str] = set()

    for host in hosts:
        name = str(host.get("name") or "").strip()
        if not name:
            warnings.append("Skipped host with empty name.")
            continue
        if name in seen_hosts:
            warnings.append(f"Duplicate host '{name}' skipped in bundle build.")
            continue
        seen_hosts.add(name)
        prepared_hosts.append(dict(host))

    for asset in ip_assets:
        ip_address = str(asset.get("ip_address") or "").strip()
        if not ip_address:
            warnings.append("Skipped asset with empty ip_address.")
            continue
        if ip_address in seen_ips:
            warnings.append(f"Duplicate IP '{ip_address}' skipped in bundle build.")
            continue
        seen_ips.add(ip_address)
        prepared_assets.append(dict(asset))

    bundle = {
        "app": "ipocket",
        "schema_version": "1",
        "exported_at": export_timestamp,
        "data": {
            "vendors": [],
            "projects": [],
            "hosts": prepared_hosts,
            "ip_assets": prepared_assets,
        },
    }
    return bundle, warnings


def write_bundle_json(bundle: dict[str, object], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(bundle, output_file, indent=2)
        output_file.write("\n")


def import_bundle_via_pipeline(
    connection,
    *,
    bundle: dict[str, object],
    user: object | None,
    dry_run: bool,
) -> ImportApplyResult:
    bundle_payload = json.dumps(bundle, ensure_ascii=False).encode("utf-8")
    return run_import(
        connection,
        BundleImporter(),
        {"bundle": bundle_payload},
        dry_run=dry_run,
        audit_context=ImportAuditContext(
            user=user,
            source="connector_ceph",
            mode="apply" if not dry_run else "dry-run",
            input_label="connector:ceph",
        ),
    )


def _print_import_result(result: ImportApplyResult) -> None:
    total = result.summary.total()
    print(
        f"Import summary: create={total.would_create}, update={total.would_update}, skip={total.would_skip}"
    )
    if result.errors:
        print("Import errors:")
        for issue in result.errors:
            print(f"- {issue.location}: {issue.message}")
    if result.warnings:
        print("Import warnings:")
        for issue in result.warnings:
            print(f"- {issue.location}: {issue.message}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import Ceph host IPs into ipocket.")
    parser.add_argument("--ceph-url", required=True, help="Ceph Dashboard base URL")
    parser.add_argument("--username", required=True, help="Ceph Dashboard username")
    parser.add_argument("--password", required=True, help="Ceph Dashboard password")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for Ceph Dashboard calls.",
    )
    parser.add_argument(
        "--mode",
        choices=("file", "dry-run", "apply"),
        default="file",
        help="file=write bundle only, dry-run/apply=run local import pipeline.",
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Path to save bundle.json (required in file mode).",
    )
    parser.add_argument(
        "--asset-type",
        choices=[asset_type.value for asset_type in IPAssetType],
        default=IPAssetType.OTHER.value,
        help="Asset type for imported IPs (default: OTHER).",
    )
    parser.add_argument("--project-name", required=False, help="Optional project name")
    parser.add_argument(
        "--tags",
        required=False,
        help="Optional comma-separated tags (example: ceph,nodes)",
    )
    parser.add_argument(
        "--note",
        required=False,
        help="Optional fixed note to apply to imported IP assets.",
    )
    parser.add_argument(
        "--include-cluster-name-tag",
        action="store_true",
        help="Add the Ceph cluster_name as a normalized tag when available.",
    )
    parser.add_argument(
        "--include-label-tags",
        action="store_true",
        help="Add normalized Ceph host labels as tags on imported IP assets.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for Ceph calls (default: 30)",
    )
    parser.add_argument("--db-path", required=False, help="Path to local ipocket DB.")
    return parser


def _validate_cli_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    if args.mode == "file" and not args.output:
        parser.error("--output is required when --mode=file")
    if args.mode in {"dry-run", "apply"} and not args.db_path:
        parser.error("--db-path is required when --mode is dry-run/apply")
    if args.timeout <= 0:
        parser.error("--timeout must be a positive integer")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_cli_args(parser, args)

    note_value = (args.note or "").strip() if args.note is not None else None
    note = note_value if note_value else None

    try:
        records = fetch_ceph_hosts(
            ceph_url=args.ceph_url,
            username=args.username,
            password=args.password,
            insecure=args.insecure,
            timeout=args.timeout,
        )
        hosts, ip_assets, extraction_warnings = extract_inventory_from_hosts(
            records,
            default_type=args.asset_type,
            project_name=args.project_name,
            tags=split_tag_string(args.tags) if args.tags else None,
            note=note,
            include_cluster_name_tag=args.include_cluster_name_tag,
            include_label_tags=args.include_label_tags,
        )
        bundle, bundle_warnings = build_import_bundle_from_ceph(hosts, ip_assets)

        for warning in [*extraction_warnings, *bundle_warnings]:
            print(f"Warning: {warning}")

        if args.mode == "file":
            write_bundle_json(bundle, args.output)
            print(
                f"Wrote Ceph import bundle with {len(hosts)} hosts and {len(ip_assets)} IP assets to {args.output}"
            )
            return 0

        from app import db

        connection = db.connect(args.db_path)
        try:
            db.init_db(connection)
            result = import_bundle_via_pipeline(
                connection,
                bundle=bundle,
                user=None,
                dry_run=args.mode == "dry-run",
            )
            _print_import_result(result)
            return 1 if result.errors else 0
        finally:
            connection.close()
    except CephConnectorError as exc:
        print(f"Connector failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
