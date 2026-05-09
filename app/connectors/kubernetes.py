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


class KubernetesConnectorError(Exception):
    pass


@dataclass(frozen=True)
class KubernetesNodeRecord:
    name: str
    internal_ips: tuple[str, ...] = ()
    labels: dict[str, str] | None = None
    cluster_name: Optional[str] = None


class KubernetesNodeRecords(list[KubernetesNodeRecord]):
    def __init__(
        self,
        records: Sequence[KubernetesNodeRecord] = (),
        *,
        cluster_name: Optional[str] = None,
    ):
        super().__init__(records)
        self.cluster_name = cluster_name


def _build_ssl_context(*, insecure: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _nodes_url(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/api/v1/nodes"


def _request_json(
    *,
    url: str,
    token: str,
    timeout: int,
    context: ssl.SSLContext,
) -> object:
    request = urllib_request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout,
            context=context,
        ) as response:
            payload = response.read()
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise KubernetesConnectorError(
            f"Kubernetes API request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise KubernetesConnectorError(f"Failed to call Kubernetes API: {exc}") from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KubernetesConnectorError("Kubernetes API returned invalid JSON.") from exc


def _extract_node_payloads(
    payload: object,
) -> tuple[list[dict[str, object]], Optional[str]]:
    if not isinstance(payload, dict):
        raise KubernetesConnectorError(
            "Kubernetes node response was not a JSON object."
        )

    cluster_name = (
        str(payload.get("cluster_name")).strip()
        if payload.get("cluster_name") is not None
        else None
    ) or None
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("clusterName") is not None:
        cluster_name = str(metadata.get("clusterName")).strip() or cluster_name

    items = payload.get("items")
    if not isinstance(items, list):
        raise KubernetesConnectorError(
            "Kubernetes node response did not include an items list."
        )
    return [item for item in items if isinstance(item, dict)], cluster_name


def _normalize_labels(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    labels: dict[str, str] = {}
    for key, raw_value in value.items():
        label_key = str(key).strip()
        label_value = str(raw_value).strip()
        if label_key and label_value:
            labels[label_key] = label_value
    return labels


def _extract_internal_ips(node_payload: dict[str, object]) -> tuple[str, ...]:
    status_payload = node_payload.get("status")
    if not isinstance(status_payload, dict):
        return ()
    addresses = status_payload.get("addresses")
    if not isinstance(addresses, list):
        return ()
    internal_ips: list[str] = []
    for address in addresses:
        if not isinstance(address, dict):
            continue
        if str(address.get("type") or "").strip() != "InternalIP":
            continue
        value = str(address.get("address") or "").strip()
        if value:
            internal_ips.append(value)
    return tuple(internal_ips)


def fetch_kubernetes_nodes(
    *,
    api_url: str,
    token: str,
    insecure: bool = False,
    timeout: int = 30,
) -> KubernetesNodeRecords:
    payload = _request_json(
        url=_nodes_url(api_url),
        token=token,
        timeout=timeout,
        context=_build_ssl_context(insecure=insecure),
    )
    node_payloads, cluster_name = _extract_node_payloads(payload)
    records: list[KubernetesNodeRecord] = []
    for node_payload in node_payloads:
        metadata = node_payload.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        name = str(metadata.get("name") or "").strip()
        labels = _normalize_labels(metadata.get("labels"))
        records.append(
            KubernetesNodeRecord(
                name=name,
                internal_ips=_extract_internal_ips(node_payload),
                labels=labels,
                cluster_name=cluster_name,
            )
        )
    return KubernetesNodeRecords(records, cluster_name=cluster_name)


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


def _normalize_tag(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = re.sub(r"[^a-z0-9_-]+", "-", value.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or None


def _add_unique_tag(tags: list[str], tag: str) -> None:
    if tag.strip().lower() not in {existing.strip().lower() for existing in tags}:
        tags.append(tag)


def _label_to_tag(key: str, value: str) -> Optional[str]:
    key_tag = _normalize_tag(key)
    value_tag = _normalize_tag(value)
    if not key_tag or not value_tag:
        return None
    return f"{key_tag}-{value_tag}"


def extract_inventory_from_nodes(
    records: Sequence[KubernetesNodeRecord],
    *,
    default_type: str = "OS",
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
    include_cluster_name_tag: bool = False,
    cluster_name: Optional[str] = None,
    include_label_tags: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    normalized_type = IPAssetType.normalize(default_type).value
    warnings: list[str] = []
    prepared_tags = [tag.strip() for tag in tags if tag.strip()] if tags else []
    effective_cluster_name = cluster_name or getattr(records, "cluster_name", None)

    if include_cluster_name_tag:
        if effective_cluster_name is None:
            for record in records:
                if record.cluster_name is not None:
                    effective_cluster_name = record.cluster_name
                    break
        cluster_tag = _normalize_tag(effective_cluster_name)
        if cluster_tag is None:
            warnings.append(
                "Kubernetes cluster name tag skipped: cluster name is missing or empty after normalization."
            )
        else:
            _add_unique_tag(prepared_tags, cluster_tag)

    host_entries: list[dict[str, object]] = []
    ip_assets: list[dict[str, object]] = []
    seen_hosts: set[str] = set()
    seen_ips: set[str] = set()

    for index, record in enumerate(records):
        node_name = record.name.strip()
        if not node_name:
            warnings.append(f"Kubernetes node {index + 1} skipped: name is missing.")
            continue

        if node_name not in seen_hosts:
            host_entries.append({"name": node_name})
            seen_hosts.add(node_name)

        if not record.internal_ips:
            warnings.append(f"Node '{node_name}' skipped: no InternalIP address found.")
            continue

        asset_tags = list(prepared_tags)
        if include_label_tags and record.labels:
            for key, value in sorted(record.labels.items()):
                label_tag = _label_to_tag(key, value)
                if label_tag:
                    _add_unique_tag(asset_tags, label_tag)

        for raw_ip in record.internal_ips:
            normalized_ip = _normalize_ipv4(raw_ip)
            if not normalized_ip:
                try:
                    parsed_candidate = ipaddress.ip_address(str(raw_ip or "").strip())
                except ValueError:
                    warnings.append(
                        f"Node '{node_name}' skipped InternalIP '{raw_ip or ''}': not a valid IPv4 address."
                    )
                else:
                    if parsed_candidate.version == 6:
                        warnings.append(
                            f"Node '{node_name}' skipped InternalIP '{raw_ip}': IPv6 is not supported."
                        )
                    else:
                        warnings.append(
                            f"Node '{node_name}' skipped InternalIP '{raw_ip}': not a usable IPv4 address."
                        )
                continue

            if ipaddress.ip_address(normalized_ip).is_loopback:
                warnings.append(
                    f"Node '{node_name}' skipped InternalIP '{normalized_ip}': loopback IP is not allowed."
                )
                continue
            if normalized_ip in seen_ips:
                warnings.append(
                    f"Duplicate IP '{normalized_ip}' skipped (node '{node_name}')."
                )
                continue
            seen_ips.add(normalized_ip)

            asset_payload: dict[str, object] = {
                "ip_address": normalized_ip,
                "type": normalized_type,
                "host_name": node_name,
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


def build_import_bundle_from_kubernetes(
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
            source="connector_kubernetes",
            mode="apply" if not dry_run else "dry-run",
            input_label="connector:kubernetes",
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
    parser = argparse.ArgumentParser(
        description="Import Kubernetes node InternalIP addresses into ipocket."
    )
    parser.add_argument("--api-url", required=True, help="Kubernetes API base URL")
    parser.add_argument(
        "--token",
        required=True,
        help="Kubernetes bearer token with permission to list nodes.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for Kubernetes API calls.",
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
        default=IPAssetType.OS.value,
        help="Asset type for imported IPs (default: OS).",
    )
    parser.add_argument("--project-name", required=False, help="Optional project name")
    parser.add_argument(
        "--tags",
        required=False,
        help="Optional comma-separated tags (example: kubernetes,nodes)",
    )
    parser.add_argument(
        "--note",
        required=False,
        help="Optional fixed note to apply to imported IP assets.",
    )
    parser.add_argument(
        "--cluster-name",
        required=False,
        help="Optional cluster name used when --include-cluster-name-tag is set.",
    )
    parser.add_argument(
        "--include-cluster-name-tag",
        action="store_true",
        help="Add the Kubernetes cluster name as a normalized tag when available.",
    )
    parser.add_argument(
        "--include-label-tags",
        action="store_true",
        help="Add normalized Kubernetes node labels as tags on imported IP assets.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for Kubernetes calls (default: 30)",
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
    cluster_name = (args.cluster_name or "").strip() or None

    try:
        records = fetch_kubernetes_nodes(
            api_url=args.api_url,
            token=args.token,
            insecure=args.insecure,
            timeout=args.timeout,
        )
        hosts, ip_assets, extraction_warnings = extract_inventory_from_nodes(
            records,
            default_type=args.asset_type,
            project_name=args.project_name,
            tags=split_tag_string(args.tags) if args.tags else None,
            note=note,
            include_cluster_name_tag=args.include_cluster_name_tag,
            cluster_name=cluster_name,
            include_label_tags=args.include_label_tags,
        )
        bundle, bundle_warnings = build_import_bundle_from_kubernetes(hosts, ip_assets)

        for warning in [*extraction_warnings, *bundle_warnings]:
            print(f"Warning: {warning}")

        if args.mode == "file":
            write_bundle_json(bundle, args.output)
            print(
                f"Wrote Kubernetes import bundle with {len(hosts)} hosts and {len(ip_assets)} IP assets to {args.output}"
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
    except KubernetesConnectorError as exc:
        print(f"Connector failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
