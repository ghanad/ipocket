from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import ssl
from typing import Optional, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.imports import BundleImporter, ImportAuditContext, run_import
from app.imports.models import ImportApplyResult
from app.models import IPAssetType
from app.utils import split_tag_string


class ElasticsearchConnectorError(Exception):
    pass


@dataclass(frozen=True)
class ElasticsearchNodeRecord:
    node_id: str
    name: str
    http_publish_address: Optional[str]
    transport_publish_address: Optional[str]
    ip: Optional[str]
    host: Optional[str]


def _build_api_key_auth_header(api_key: str) -> str:
    candidate = api_key.strip()
    if ":" in candidate:
        encoded = base64.b64encode(candidate.encode("utf-8")).decode("ascii")
        return f"ApiKey {encoded}"
    return f"ApiKey {candidate}"


def _build_basic_auth_header(username: str, password: str) -> str:
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


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


def _extract_host_candidate(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return candidate

    if candidate.startswith("inet[") and candidate.endswith("]"):
        candidate = candidate[len("inet[") : -1].strip()

    if candidate.startswith("/") and len(candidate) > 1:
        candidate = candidate[1:]

    if candidate.startswith("[") and "]" in candidate:
        bracket_index = candidate.find("]")
        if bracket_index > 1:
            suffix = candidate[bracket_index + 1 :]
            if suffix.startswith(":") and suffix[1:].isdigit():
                return candidate[1:bracket_index]
            return candidate[1:bracket_index]

    if candidate.count(":") == 1:
        host_part, port_part = candidate.rsplit(":", 1)
        if host_part and port_part.isdigit():
            return host_part

    return candidate


def fetch_elasticsearch_nodes(
    *,
    elasticsearch_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 30,
) -> list[ElasticsearchNodeRecord]:
    base_url = elasticsearch_url.rstrip("/")
    url = f"{base_url}/_nodes/http,transport"
    headers = {"Accept": "application/json"}

    if api_key:
        headers["Authorization"] = _build_api_key_auth_header(api_key)
    elif username and password is not None:
        headers["Authorization"] = _build_basic_auth_header(username, password)

    request = urllib_request.Request(url, method="GET", headers=headers)
    ssl_context = ssl._create_unverified_context()

    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout,
            context=ssl_context,
        ) as response:
            payload = response.read()
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ElasticsearchConnectorError(
            f"Elasticsearch node query failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise ElasticsearchConnectorError(
            f"Failed to call Elasticsearch API: {exc}"
        ) from exc

    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ElasticsearchConnectorError(
            "Elasticsearch API returned invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise ElasticsearchConnectorError(
            "Elasticsearch API returned an unexpected payload."
        )

    nodes = parsed.get("nodes")
    if not isinstance(nodes, dict):
        raise ElasticsearchConnectorError(
            "Elasticsearch payload is missing a valid 'nodes' object."
        )

    records: list[ElasticsearchNodeRecord] = []
    for node_id, node_payload in nodes.items():
        if not isinstance(node_payload, dict):
            continue
        node_name = str(node_payload.get("name") or str(node_id))
        http_payload = node_payload.get("http")
        transport_payload = node_payload.get("transport")
        http_publish_address = (
            str(http_payload.get("publish_address"))
            if isinstance(http_payload, dict) and http_payload.get("publish_address")
            else None
        )
        transport_publish_address = (
            str(transport_payload.get("publish_address"))
            if isinstance(transport_payload, dict)
            and transport_payload.get("publish_address")
            else None
        )
        ip_value = (
            str(node_payload.get("ip")) if node_payload.get("ip") is not None else None
        )
        host_value = (
            str(node_payload.get("host"))
            if node_payload.get("host") is not None
            else None
        )
        records.append(
            ElasticsearchNodeRecord(
                node_id=str(node_id),
                name=node_name,
                http_publish_address=http_publish_address,
                transport_publish_address=transport_publish_address,
                ip=ip_value,
                host=host_value,
            )
        )

    return records


def _pick_ip_candidate(
    record: ElasticsearchNodeRecord,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for source, candidate in (
        ("http.publish_address", record.http_publish_address),
        ("transport.publish_address", record.transport_publish_address),
        ("ip", record.ip),
        ("host", record.host),
    ):
        if isinstance(candidate, str) and candidate.strip():
            candidates.append((source, candidate))
    return candidates


def extract_ip_assets_from_nodes(
    records: Sequence[ElasticsearchNodeRecord],
    *,
    default_type: str = "OTHER",
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
) -> tuple[list[dict[str, object]], list[str]]:
    normalized_type = IPAssetType.normalize(default_type).value
    prepared_tags = [tag.strip() for tag in tags if tag.strip()] if tags else None
    warnings: list[str] = []
    ip_assets: list[dict[str, object]] = []
    seen_ips: set[str] = set()

    for record in records:
        raw_candidates = _pick_ip_candidate(record)
        node_label = record.name or record.node_id
        if not raw_candidates:
            warnings.append(
                f"Node '{node_label}' skipped: no IP candidate found in "
                "http.publish_address, transport.publish_address, ip, or host."
            )
            continue

        normalized_ip: Optional[str] = None
        skip_reason: Optional[str] = None
        for source, raw_candidate in raw_candidates:
            host_candidate = _extract_host_candidate(raw_candidate)
            normalized_ip = _normalize_ipv4(host_candidate)
            if not normalized_ip:
                try:
                    parsed_candidate = ipaddress.ip_address(host_candidate)
                except ValueError:
                    skip_reason = (
                        f"source '{source}' value '{raw_candidate}' does not contain "
                        "a valid IPv4 address."
                    )
                else:
                    if parsed_candidate.version == 6:
                        skip_reason = (
                            f"source '{source}' value '{raw_candidate}' resolved to IPv6, "
                            "but only IPv4 is supported."
                        )
                    else:
                        skip_reason = (
                            f"source '{source}' value '{raw_candidate}' is not a usable "
                            "IPv4 address."
                        )
                continue
            if ipaddress.ip_address(normalized_ip).is_loopback:
                skip_reason = f"loopback IP '{normalized_ip}' is not allowed."
                normalized_ip = None
                continue
            break

        if not normalized_ip:
            warnings.append(
                f"Node '{node_label}' skipped: {skip_reason or 'invalid IP.'}"
            )
            continue

        if normalized_ip in seen_ips:
            warnings.append(
                f"Duplicate IP '{normalized_ip}' skipped (node '{node_label}')."
            )
            continue
        seen_ips.add(normalized_ip)

        asset_payload: dict[str, object] = {
            "ip_address": normalized_ip,
            "type": normalized_type,
            "merge_tags": True,
            "archived": False,
        }
        if project_name:
            asset_payload["project_name"] = project_name
        if prepared_tags:
            asset_payload["tags"] = prepared_tags
        if note is not None:
            asset_payload["notes"] = note
            asset_payload["notes_provided"] = True

        ip_assets.append(asset_payload)

    return ip_assets, warnings


def build_import_bundle_from_elasticsearch(
    ip_assets: Sequence[dict[str, object]],
    *,
    exported_at: Optional[str] = None,
) -> tuple[dict[str, object], list[str]]:
    export_timestamp = exported_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    warnings: list[str] = []
    prepared_assets: list[dict[str, object]] = []
    seen_ips: set[str] = set()

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
            "hosts": [],
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
            source="connector_elasticsearch",
            mode="apply" if not dry_run else "dry-run",
            input_label="connector:elasticsearch",
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
        description="Import Elasticsearch node IPs into ipocket."
    )
    parser.add_argument(
        "--elasticsearch-url", required=True, help="Elasticsearch base URL"
    )
    parser.add_argument("--username", required=False, help="Elasticsearch username")
    parser.add_argument("--password", required=False, help="Elasticsearch password")
    parser.add_argument(
        "--api-key",
        required=False,
        help="Elasticsearch API key in Base64 form or id:key format.",
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
        help="Optional comma-separated tags (example: elasticsearch,nodes)",
    )
    parser.add_argument(
        "--note",
        required=False,
        help="Optional fixed note to apply to imported IP assets.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for Elasticsearch calls (default: 30)",
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

    has_api_key = bool((args.api_key or "").strip())
    has_username = bool((args.username or "").strip())
    has_password = args.password is not None

    if has_api_key and (has_username or has_password):
        parser.error("Provide either --api-key or --username/--password, not both")
    if not has_api_key:
        if has_username and not has_password:
            parser.error("--password is required when --username is provided")
        if has_password and not has_username:
            parser.error("--username is required when --password is provided")
        if not has_username and not has_password:
            parser.error(
                "Authentication is required: use --api-key or --username/--password"
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_cli_args(parser, args)

    username = (args.username or "").strip() or None
    password = args.password if args.password is not None else None
    api_key = (args.api_key or "").strip() or None
    note_value = (args.note or "").strip() if args.note is not None else None
    note = note_value if note_value else None

    try:
        records = fetch_elasticsearch_nodes(
            elasticsearch_url=args.elasticsearch_url,
            username=username,
            password=password,
            api_key=api_key,
            timeout=args.timeout,
        )
        ip_assets, extraction_warnings = extract_ip_assets_from_nodes(
            records,
            default_type=args.asset_type,
            project_name=args.project_name,
            tags=split_tag_string(args.tags) if args.tags else None,
            note=note,
        )
    except ElasticsearchConnectorError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    bundle, bundle_warnings = build_import_bundle_from_elasticsearch(ip_assets)
    all_warnings = [*extraction_warnings, *bundle_warnings]

    print(f"Collected {len(records)} Elasticsearch nodes")
    print(f"Prepared {len(ip_assets)} IP assets from node inventory")
    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(f"- {warning}")

    if args.output:
        write_bundle_json(bundle, args.output)
        print(f"Bundle written to {args.output}")

    if args.mode in {"dry-run", "apply"}:
        from app import db

        connection = db.connect(args.db_path)
        try:
            result = import_bundle_via_pipeline(
                connection,
                bundle=bundle,
                user=None,
                dry_run=args.mode == "dry-run",
            )
        finally:
            connection.close()

        print(f"ipocket import mode: {args.mode}")
        _print_import_result(result)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
