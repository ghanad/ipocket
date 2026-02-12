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
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from app.models import IPAssetType
from app.utils import split_tag_string


class PrometheusConnectorError(Exception):
    pass


@dataclass(frozen=True)
class PrometheusMetricRecord:
    labels: dict[str, str]
    value: str


def _build_prometheus_auth_header(auth_value: str) -> str:
    candidate = auth_value.strip()
    if ":" in candidate:
        encoded = base64.b64encode(candidate.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"
    return f"Bearer {candidate}"



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

    if candidate.startswith("[") and "]" in candidate:
        bracket_index = candidate.find("]")
        if bracket_index > 1:
            suffix = candidate[bracket_index + 1 :]
            if suffix.startswith(":") and suffix[1:].isdigit():
                return candidate[1:bracket_index]

    if candidate.count(":") == 1:
        host_part, port_part = candidate.rsplit(":", 1)
        if host_part and port_part.isdigit():
            return host_part

    return candidate



def fetch_prometheus_query_result(
    *,
    prometheus_url: str,
    query: str,
    token: Optional[str] = None,
    timeout: int = 30,
    insecure: bool = False,
) -> list[PrometheusMetricRecord]:
    base_url = prometheus_url.rstrip("/")
    encoded_query = urllib_parse.urlencode({"query": query})
    url = f"{base_url}/api/v1/query?{encoded_query}"

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = _build_prometheus_auth_header(token)

    request = urllib_request.Request(url, method="GET", headers=headers)
    ssl_context = ssl._create_unverified_context() if insecure else None

    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout,
            context=ssl_context,
        ) as response:
            response_payload = response.read()
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise PrometheusConnectorError(
            f"Prometheus query failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise PrometheusConnectorError(f"Failed to call Prometheus API: {exc}") from exc

    try:
        parsed = json.loads(response_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrometheusConnectorError("Prometheus API returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise PrometheusConnectorError("Prometheus API returned an unexpected payload.")

    status_value = parsed.get("status")
    if status_value != "success":
        error_type = parsed.get("errorType")
        error_message = parsed.get("error")
        raise PrometheusConnectorError(
            "Prometheus query status was not success"
            + (
                f" ({error_type}: {error_message})."
                if error_type or error_message
                else "."
            )
        )

    data = parsed.get("data")
    if not isinstance(data, dict):
        raise PrometheusConnectorError("Prometheus payload is missing data.")

    result_type = data.get("resultType")
    if result_type != "vector":
        raise PrometheusConnectorError(
            f"Unsupported Prometheus resultType '{result_type}'. Expected 'vector'."
        )

    result = data.get("result")
    if not isinstance(result, list):
        raise PrometheusConnectorError("Prometheus payload contains invalid result list.")

    records: list[PrometheusMetricRecord] = []
    for index, sample in enumerate(result):
        if not isinstance(sample, dict):
            raise PrometheusConnectorError(
                f"Prometheus sample at index {index} is not an object."
            )
        metric = sample.get("metric")
        value = sample.get("value")
        if not isinstance(metric, dict):
            raise PrometheusConnectorError(
                f"Prometheus sample at index {index} has invalid metric labels."
            )
        if not isinstance(value, list) or len(value) != 2:
            raise PrometheusConnectorError(
                f"Prometheus sample at index {index} has invalid value field."
            )
        label_map: dict[str, str] = {}
        for key, label_value in metric.items():
            if key is None:
                continue
            label_map[str(key)] = str(label_value)
        records.append(PrometheusMetricRecord(labels=label_map, value=str(value[1])))

    return records



def extract_ip_assets_from_result(
    records: Sequence[PrometheusMetricRecord],
    *,
    ip_label: str,
    default_type: str = "OTHER",
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    query: Optional[str] = None,
    notes_template: str = (
        "Imported from Prometheus query '{query}' using label '{ip_label}' "
        "(metric={metric_name}, value={sample_value})."
    ),
) -> tuple[list[dict[str, object]], list[str]]:
    normalized_type = IPAssetType.normalize(default_type).value
    normalized_label = ip_label.strip()
    if not normalized_label:
        raise PrometheusConnectorError("IP label must not be empty.")

    prepared_tags = [tag.strip() for tag in tags if tag.strip()] if tags else None
    warnings: list[str] = []
    ip_assets: list[dict[str, object]] = []
    seen_ips: set[str] = set()

    for index, record in enumerate(records):
        raw_label_value = record.labels.get(normalized_label)
        if raw_label_value is None:
            warnings.append(
                f"Sample {index} skipped: label '{normalized_label}' is missing."
            )
            continue

        host_candidate = _extract_host_candidate(raw_label_value)
        normalized_ip = _normalize_ipv4(host_candidate)
        if not normalized_ip:
            warnings.append(
                "Sample "
                f"{index} skipped: label '{normalized_label}' value "
                f"'{raw_label_value}' does not contain a valid IPv4 address."
            )
            continue

        if ipaddress.ip_address(normalized_ip).is_loopback:
            warnings.append(
                f"Sample {index} skipped: loopback IP '{normalized_ip}' is not allowed."
            )
            continue

        if normalized_ip in seen_ips:
            warnings.append(f"Duplicate IP '{normalized_ip}' skipped.")
            continue
        seen_ips.add(normalized_ip)

        metric_name = record.labels.get("__name__", "unknown")
        rendered_query = query if query is not None else "<not-provided>"
        notes = notes_template.format(
            query=rendered_query,
            ip_label=normalized_label,
            metric_name=metric_name,
            sample_value=record.value,
        )
        asset_payload: dict[str, object] = {
            "ip_address": normalized_ip,
            "type": normalized_type,
            "notes": notes,
            "archived": False,
        }
        if project_name:
            asset_payload["project_name"] = project_name
        if prepared_tags:
            asset_payload["tags"] = prepared_tags

        ip_assets.append(asset_payload)

    return ip_assets, warnings



def build_import_bundle_from_prometheus(
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
    boundary = "----ipocket-prometheus-boundary"
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
        raise PrometheusConnectorError(
            f"ipocket import request failed with HTTP {exc.code}: {details}"
        ) from exc
    except urllib_error.URLError as exc:
        raise PrometheusConnectorError(f"Failed to call ipocket import API: {exc}") from exc

    try:
        parsed = json.loads(response_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrometheusConnectorError(
            "ipocket import API returned invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise PrometheusConnectorError(
            "ipocket import API returned an unexpected payload."
        )
    return parsed



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



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import IP assets from Prometheus query results into ipocket."
    )
    parser.add_argument("--prometheus-url", required=True, help="Prometheus base URL")
    parser.add_argument("--query", required=True, help="PromQL query")
    parser.add_argument(
        "--ip-label",
        required=True,
        help="Metric label that contains IP or host:port (example: instance)",
    )
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
        "--asset-type",
        choices=[asset_type.value for asset_type in IPAssetType],
        default=IPAssetType.OTHER.value,
        help="Asset type for imported IPs (default: OTHER).",
    )
    parser.add_argument("--project-name", required=False, help="Optional project name")
    parser.add_argument(
        "--tags",
        required=False,
        help="Optional comma-separated tags (example: monitoring,node-exporter)",
    )
    parser.add_argument(
        "--token",
        required=False,
        help="Optional Prometheus auth value: Bearer token or username:password.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification for Prometheus HTTPS calls.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds for Prometheus/API calls (default: 30)",
    )
    parser.add_argument(
        "--ipocket-url",
        required=False,
        help="ipocket base URL (example: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--ipocket-token",
        required=False,
        help="Bearer token for ipocket API auth.",
    )
    parser.add_argument(
        "--ipocket-insecure",
        action="store_true",
        help="Disable TLS verification for ipocket API HTTPS calls.",
    )
    return parser



def _validate_cli_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    if args.mode == "file" and not args.output:
        parser.error("--output is required when --mode=file")
    if args.mode in {"dry-run", "apply"} and not args.ipocket_url:
        parser.error("--ipocket-url is required when --mode is dry-run/apply")
    if args.mode in {"dry-run", "apply"} and not args.ipocket_token:
        parser.error("--ipocket-token is required when --mode is dry-run/apply")



def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_cli_args(parser, args)

    try:
        records = fetch_prometheus_query_result(
            prometheus_url=args.prometheus_url,
            query=args.query,
            token=args.token,
            timeout=args.timeout,
            insecure=args.insecure,
        )
        ip_assets, extraction_warnings = extract_ip_assets_from_result(
            records,
            ip_label=args.ip_label,
            default_type=args.asset_type,
            project_name=args.project_name,
            tags=split_tag_string(args.tags) if args.tags else None,
            query=args.query,
        )
    except PrometheusConnectorError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    bundle, bundle_warnings = build_import_bundle_from_prometheus(ip_assets)
    all_warnings = [*extraction_warnings, *bundle_warnings]

    print(f"Collected {len(records)} metric samples from Prometheus")
    print(f"Prepared {len(ip_assets)} IP assets from query results")
    if all_warnings:
        print("Warnings:")
        for warning in all_warnings:
            print(f"- {warning}")

    if args.output:
        write_bundle_json(bundle, args.output)
        print(f"Bundle written to {args.output}")

    if args.mode in {"dry-run", "apply"}:
        try:
            result = import_bundle_via_api(
                bundle=bundle,
                ipocket_url=args.ipocket_url,
                token=args.ipocket_token,
                dry_run=args.mode == "dry-run",
                insecure=args.ipocket_insecure,
                timeout_seconds=args.timeout,
            )
        except PrometheusConnectorError as exc:
            parser.exit(status=1, message=f"error: {exc}\n")

        print(f"ipocket import mode: {args.mode}")
        _print_import_result(result)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
