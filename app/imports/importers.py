from __future__ import annotations

import csv
import io
import json
from typing import Optional, Protocol

from app.imports.models import (
    ImportBundle,
    ImportHost,
    ImportIPAsset,
    ImportParseError,
    ImportProject,
    ImportSource,
    ImportVendor,
)


class Importer(Protocol):
    def parse(self, inputs: dict[str, bytes], options: Optional[dict[str, object]] = None) -> ImportBundle:
        ...


class BundleImporter:
    def parse(self, inputs: dict[str, bytes], options: Optional[dict[str, object]] = None) -> ImportBundle:
        if "bundle" not in inputs:
            raise ImportParseError("Missing bundle.json input.")
        try:
            payload = json.loads(inputs["bundle"].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ImportParseError("Invalid JSON payload.") from exc

        if payload.get("schema_version") != "1":
            raise ImportParseError("Unsupported schema_version (expected '1').", location="schema_version")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ImportParseError("Missing data section.", location="data")

        bundle = ImportBundle()
        bundle.vendors = _parse_named_entities(data.get("vendors"), "data.vendors")
        bundle.projects = _parse_projects(data.get("projects"), "data.projects")
        bundle.hosts = _parse_hosts(data.get("hosts"), "data.hosts")
        bundle.ip_assets = _parse_ip_assets(data.get("ip_assets"), "data.ip_assets")
        return bundle


def _parse_named_entities(section: object, base_path: str) -> list[ImportVendor]:
    if section is None:
        return []
    if not isinstance(section, list):
        raise ImportParseError("Expected a list.", location=base_path)
    vendors: list[ImportVendor] = []
    for index, entry in enumerate(section):
        if not isinstance(entry, dict):
            raise ImportParseError("Expected object entries.", location=f"{base_path}[{index}]")
        vendors.append(
            ImportVendor(
                name=str(entry.get("name") or ""),
                source=ImportSource(f"{base_path}[{index}]"),
            )
        )
    return vendors


def _parse_projects(section: object, base_path: str) -> list[ImportProject]:
    if section is None:
        return []
    if not isinstance(section, list):
        raise ImportParseError("Expected a list.", location=base_path)
    projects: list[ImportProject] = []
    for index, entry in enumerate(section):
        if not isinstance(entry, dict):
            raise ImportParseError("Expected object entries.", location=f"{base_path}[{index}]")
        projects.append(
            ImportProject(
                name=str(entry.get("name") or ""),
                description=_normalize_optional_str(entry.get("description")),
                color=_normalize_optional_str(entry.get("color")),
                source=ImportSource(f"{base_path}[{index}]"),
            )
        )
    return projects


def _parse_hosts(section: object, base_path: str) -> list[ImportHost]:
    if section is None:
        return []
    if not isinstance(section, list):
        raise ImportParseError("Expected a list.", location=base_path)
    hosts: list[ImportHost] = []
    for index, entry in enumerate(section):
        if not isinstance(entry, dict):
            raise ImportParseError("Expected object entries.", location=f"{base_path}[{index}]")
        hosts.append(
            ImportHost(
                name=str(entry.get("name") or ""),
                notes=_normalize_optional_str(entry.get("notes")),
                vendor_name=_normalize_optional_str(entry.get("vendor_name")),
                source=ImportSource(f"{base_path}[{index}]"),
            )
        )
    return hosts


def _parse_ip_assets(section: object, base_path: str) -> list[ImportIPAsset]:
    if section is None:
        return []
    if not isinstance(section, list):
        raise ImportParseError("Expected a list.", location=base_path)
    assets: list[ImportIPAsset] = []
    for index, entry in enumerate(section):
        if not isinstance(entry, dict):
            raise ImportParseError("Expected object entries.", location=f"{base_path}[{index}]")
        assets.append(
            ImportIPAsset(
                ip_address=str(entry.get("ip_address") or ""),
                subnet=_normalize_optional_str(entry.get("subnet")),
                gateway=_normalize_optional_str(entry.get("gateway")),
                asset_type=str(entry.get("type") or ""),
                project_name=_normalize_optional_str(entry.get("project_name")),
                host_name=_normalize_optional_str(entry.get("host_name")),
                notes=_normalize_optional_str(entry.get("notes")),
                archived=_normalize_optional_bool(entry.get("archived")),
                source=ImportSource(f"{base_path}[{index}]"),
            )
        )
    return assets


class CsvImporter:
    def parse(self, inputs: dict[str, bytes], options: Optional[dict[str, object]] = None) -> ImportBundle:
        if "hosts" not in inputs or "ip_assets" not in inputs:
            raise ImportParseError("CSV import requires hosts.csv and ip-assets.csv inputs.")

        hosts = _parse_hosts_csv(inputs["hosts"], "hosts.csv")
        ip_assets = _parse_ip_assets_csv(inputs["ip_assets"], "ip-assets.csv")
        vendors = _derive_vendors_from_hosts(hosts)
        projects = _derive_projects_from_ip_assets(ip_assets)
        return ImportBundle(vendors=vendors, projects=projects, hosts=hosts, ip_assets=ip_assets)


def _parse_hosts_csv(data: bytes, filename: str) -> list[ImportHost]:
    rows, fieldnames = _read_csv(data)
    _require_columns(fieldnames, {"name", "notes", "vendor_name"}, filename)
    hosts: list[ImportHost] = []
    for row, line_number in rows:
        hosts.append(
            ImportHost(
                name=str(row.get("name") or ""),
                notes=_normalize_optional_str(row.get("notes")),
                vendor_name=_normalize_optional_str(row.get("vendor_name")),
                source=ImportSource(f"{filename}:line {line_number}"),
            )
        )
    return hosts


def _parse_ip_assets_csv(data: bytes, filename: str) -> list[ImportIPAsset]:
    rows, fieldnames = _read_csv(data)
    _require_columns(
        fieldnames,
        {"ip_address", "subnet", "gateway", "type", "project_name", "host_name", "notes", "archived"},
        filename,
    )
    assets: list[ImportIPAsset] = []
    for row, line_number in rows:
        assets.append(
            ImportIPAsset(
                ip_address=str(row.get("ip_address") or ""),
                subnet=_normalize_optional_str(row.get("subnet")),
                gateway=_normalize_optional_str(row.get("gateway")),
                asset_type=str(row.get("type") or ""),
                project_name=_normalize_optional_str(row.get("project_name")),
                host_name=_normalize_optional_str(row.get("host_name")),
                notes=_normalize_optional_str(row.get("notes")),
                archived=_normalize_optional_bool(row.get("archived")),
                source=ImportSource(f"{filename}:line {line_number}"),
            )
        )
    return assets


def _derive_vendors_from_hosts(hosts: list[ImportHost]) -> list[ImportVendor]:
    seen: set[str] = set()
    vendors: list[ImportVendor] = []
    for host in hosts:
        if host.vendor_name:
            if host.vendor_name not in seen:
                seen.add(host.vendor_name)
                vendors.append(ImportVendor(name=host.vendor_name, source=host.source))
    return vendors


def _derive_projects_from_ip_assets(ip_assets: list[ImportIPAsset]) -> list[ImportProject]:
    seen: set[str] = set()
    projects: list[ImportProject] = []
    for asset in ip_assets:
        if asset.project_name:
            if asset.project_name not in seen:
                seen.add(asset.project_name)
                projects.append(ImportProject(name=asset.project_name, source=asset.source))
    return projects


def _normalize_optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return str(value).strip() or None


def _normalize_optional_bool(value: object) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def _read_csv(data: bytes) -> tuple[list[tuple[dict[str, str], int]], list[str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportParseError("CSV is not valid UTF-8.") from exc
    buffer = io.StringIO(text)
    reader = csv.DictReader(buffer)
    rows: list[tuple[dict[str, str], int]] = []
    for row in reader:
        rows.append((row, reader.line_num))
    return rows, reader.fieldnames or []


def _require_columns(fieldnames: list[str], required: set[str], filename: str) -> None:
    missing = sorted(required.difference(fieldnames))
    if missing:
        raise ImportParseError(
            f"Missing required columns: {', '.join(missing)}.",
            location=filename,
        )
