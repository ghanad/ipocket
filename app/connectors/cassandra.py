from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import re
import ssl
from typing import Optional, Sequence

from app.imports import BundleImporter, ImportAuditContext, run_import
from app.imports.models import ImportApplyResult
from app.models import IPAssetType
from app.utils import split_tag_string


class CassandraConnectorError(Exception):
    pass


@dataclass(frozen=True)
class CassandraNodeRecord:
    address: str
    datacenter: Optional[str] = None
    rack: Optional[str] = None
    host_id: Optional[str] = None
    cluster_name: Optional[str] = None


class CassandraNodeRecords(list[CassandraNodeRecord]):
    def __init__(
        self,
        records: Sequence[CassandraNodeRecord] = (),
        *,
        cluster_name: Optional[str] = None,
    ):
        super().__init__(records)
        self.cluster_name = cluster_name


def parse_contact_points(value: str | Sequence[str]) -> list[str]:
    raw_values: Sequence[str]
    if isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = value

    contact_points: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        candidate = str(raw_value).strip()
        if not candidate:
            continue
        if candidate not in seen:
            contact_points.append(candidate)
            seen.add(candidate)
    if not contact_points:
        raise CassandraConnectorError(
            "At least one Cassandra contact point is required."
        )
    return contact_points


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


def _normalize_cluster_name_tag(cluster_name: Optional[str]) -> Optional[str]:
    if cluster_name is None:
        return None
    normalized = re.sub(r"[^a-z0-9_-]+", "-", cluster_name.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or None


def _build_ssl_context(*, insecure: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _records_from_metadata_hosts(
    hosts: Sequence[object],
    *,
    cluster_name: Optional[str],
) -> CassandraNodeRecords:
    records: list[CassandraNodeRecord] = []
    for host in hosts:
        address = str(getattr(host, "address", "") or "").strip()
        records.append(
            CassandraNodeRecord(
                address=address,
                datacenter=(
                    str(getattr(host, "datacenter", "")).strip()
                    if getattr(host, "datacenter", None) is not None
                    else None
                )
                or None,
                rack=(
                    str(getattr(host, "rack", "")).strip()
                    if getattr(host, "rack", None) is not None
                    else None
                )
                or None,
                host_id=(
                    str(getattr(host, "host_id", "")).strip()
                    if getattr(host, "host_id", None) is not None
                    else None
                )
                or None,
                cluster_name=cluster_name,
            )
        )
    return CassandraNodeRecords(records, cluster_name=cluster_name)


def fetch_cassandra_nodes(
    *,
    contact_points: Sequence[str],
    port: int = 9042,
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_tls: bool = False,
    insecure: bool = False,
    timeout: int = 30,
) -> CassandraNodeRecords:
    try:
        from cassandra.auth import PlainTextAuthProvider
        from cassandra.cluster import Cluster
    except ImportError as exc:
        raise CassandraConnectorError(
            "Missing dependency 'cassandra-driver'. Install it with: pip install -r requirements.txt"
        ) from exc

    cluster_kwargs: dict[str, object] = {
        "contact_points": list(contact_points),
        "port": port,
        "connect_timeout": timeout,
    }
    if username and password is not None:
        cluster_kwargs["auth_provider"] = PlainTextAuthProvider(
            username=username,
            password=password,
        )
    if use_tls:
        cluster_kwargs["ssl_context"] = _build_ssl_context(insecure=insecure)

    cluster = None
    session = None
    try:
        cluster = Cluster(**cluster_kwargs)
        session = cluster.connect()
        metadata = cluster.metadata
        cluster_name = (
            str(getattr(metadata, "cluster_name", "")).strip()
            if getattr(metadata, "cluster_name", None) is not None
            else None
        ) or None
        hosts = list(metadata.all_hosts())
        return _records_from_metadata_hosts(hosts, cluster_name=cluster_name)
    except Exception as exc:
        raise CassandraConnectorError(
            f"Failed to read Cassandra cluster metadata: {exc}"
        ) from exc
    finally:
        if session is not None:
            session.shutdown()
        if cluster is not None:
            cluster.shutdown()


def extract_ip_assets_from_nodes(
    records: Sequence[CassandraNodeRecord],
    *,
    default_type: str = "OTHER",
    project_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    note: Optional[str] = None,
    include_cluster_name_tag: bool = False,
) -> tuple[list[dict[str, object]], list[str]]:
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
                "Cassandra cluster name tag skipped: cluster_name is missing or empty after normalization."
            )
        elif cluster_tag not in {tag.strip().lower() for tag in prepared_tags}:
            prepared_tags.append(cluster_tag)

    ip_assets: list[dict[str, object]] = []
    seen_ips: set[str] = set()

    for index, record in enumerate(records):
        node_label = record.host_id or record.address or f"node-{index}"
        normalized_ip = _normalize_ipv4(record.address)
        if not normalized_ip:
            try:
                parsed_candidate = ipaddress.ip_address(str(record.address).strip())
            except ValueError:
                warnings.append(
                    f"Node '{node_label}' skipped: address '{record.address}' does not contain a valid IPv4 address."
                )
            else:
                if parsed_candidate.version == 6:
                    warnings.append(
                        f"Node '{node_label}' skipped: address '{record.address}' resolved to IPv6, but only IPv4 is supported."
                    )
                else:
                    warnings.append(
                        f"Node '{node_label}' skipped: address '{record.address}' is not a usable IPv4 address."
                    )
            continue

        if ipaddress.ip_address(normalized_ip).is_loopback:
            warnings.append(
                f"Node '{node_label}' skipped: loopback IP '{normalized_ip}' is not allowed."
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


def build_import_bundle_from_cassandra(
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
            source="connector_cassandra",
            mode="apply" if not dry_run else "dry-run",
            input_label="connector:cassandra",
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
        description="Import Cassandra node IPs into ipocket."
    )
    parser.add_argument(
        "--contact-points",
        required=True,
        help="Comma-separated Cassandra contact points",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9042,
        help="Cassandra native protocol port (default: 9042)",
    )
    parser.add_argument("--username", required=False, help="Cassandra username")
    parser.add_argument("--password", required=False, help="Cassandra password")
    parser.add_argument(
        "--use-tls",
        action="store_true",
        help="Enable TLS for the Cassandra connection.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification when --use-tls is set.",
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
        help="Optional comma-separated tags (example: cassandra,nodes)",
    )
    parser.add_argument(
        "--note",
        required=False,
        help="Optional fixed note to apply to imported IP assets.",
    )
    parser.add_argument(
        "--include-cluster-name-tag",
        action="store_true",
        help="Add the Cassandra cluster_name as a normalized tag on every imported IP asset.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Connection timeout in seconds for Cassandra calls (default: 30)",
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
    if args.port <= 0 or args.port > 65535:
        parser.error("--port must be a valid number between 1 and 65535")
    if args.timeout <= 0:
        parser.error("--timeout must be a positive integer")
    if args.insecure and not args.use_tls:
        parser.error("--insecure requires --use-tls")

    has_username = bool((args.username or "").strip())
    has_password = args.password is not None
    if has_username and not has_password:
        parser.error("--password is required when --username is provided")
    if has_password and not has_username:
        parser.error("--username is required when --password is provided")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_cli_args(parser, args)

    username = (args.username or "").strip() or None
    password = args.password if args.password is not None else None
    note_value = (args.note or "").strip() if args.note is not None else None
    note = note_value if note_value else None

    try:
        records = fetch_cassandra_nodes(
            contact_points=parse_contact_points(args.contact_points),
            port=args.port,
            username=username,
            password=password,
            use_tls=args.use_tls,
            insecure=args.insecure,
            timeout=args.timeout,
        )
        ip_assets, extraction_warnings = extract_ip_assets_from_nodes(
            records,
            default_type=args.asset_type,
            project_name=args.project_name,
            tags=split_tag_string(args.tags) if args.tags else None,
            note=note,
            include_cluster_name_tag=args.include_cluster_name_tag,
        )
        bundle, bundle_warnings = build_import_bundle_from_cassandra(ip_assets)

        for warning in [*extraction_warnings, *bundle_warnings]:
            print(f"Warning: {warning}")

        if args.mode == "file":
            write_bundle_json(bundle, args.output)
            print(
                f"Wrote Cassandra import bundle with {len(ip_assets)} IP assets to {args.output}"
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
    except CassandraConnectorError as exc:
        print(f"Connector failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
