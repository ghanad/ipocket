from __future__ import annotations

import ipaddress

from app import repository
from app.imports.models import ImportBundle, ImportIssue, ImportValidationResult
from app.models import IPAssetType
from app.utils import normalize_hex_color, normalize_tag_name


def validate_bundle(connection, bundle: ImportBundle) -> ImportValidationResult:
    result = ImportValidationResult()

    vendor_names = {vendor.name.strip() for vendor in bundle.vendors if vendor.name}
    project_names = {
        project.name.strip() for project in bundle.projects if project.name
    }
    host_names = {host.name.strip() for host in bundle.hosts if host.name}

    existing_vendor_names = {
        vendor.name for vendor in repository.list_vendors(connection)
    }
    existing_project_names = {
        project.name for project in repository.list_projects(connection)
    }
    existing_host_names = {host.name for host in repository.list_hosts(connection)}

    for vendor in bundle.vendors:
        if not vendor.name.strip():
            result.errors.append(_issue(vendor.source, "Vendor name is required."))

    for project in bundle.projects:
        if not project.name.strip():
            result.errors.append(_issue(project.source, "Project name is required."))
        if project.color:
            try:
                normalize_hex_color(project.color)
            except ValueError as exc:
                result.errors.append(
                    _issue(_with_field(project.source, "color"), str(exc))
                )

    for host in bundle.hosts:
        if not host.name.strip():
            result.errors.append(_issue(host.source, "Host name is required."))
        if host.vendor_name:
            if (
                host.vendor_name not in vendor_names
                and host.vendor_name not in existing_vendor_names
            ):
                result.errors.append(
                    _issue(
                        _with_field(host.source, "vendor_name"),
                        "Vendor does not exist.",
                    )
                )

    for asset in bundle.ip_assets:
        if not asset.ip_address.strip():
            result.errors.append(_issue(asset.source, "IP address is required."))
        else:
            if not _is_valid_ip(asset.ip_address):
                result.errors.append(
                    _issue(
                        _with_field(asset.source, "ip_address"), "Invalid IP address."
                    )
                )
        if not asset.asset_type.strip():
            result.errors.append(
                _issue(_with_field(asset.source, "type"), "Asset type is required.")
            )
        else:
            if not _is_valid_asset_type(asset.asset_type):
                result.errors.append(
                    _issue(
                        _with_field(asset.source, "type"),
                        "Invalid asset type. Use OS, BMC, VM, VIP, OTHER.",
                    )
                )
        if asset.project_name:
            if (
                asset.project_name not in project_names
                and asset.project_name not in existing_project_names
            ):
                result.errors.append(
                    _issue(
                        _with_field(asset.source, "project_name"),
                        "Project does not exist.",
                    )
                )
        if asset.host_name:
            if (
                asset.host_name not in host_names
                and asset.host_name not in existing_host_names
            ):
                result.errors.append(
                    _issue(
                        _with_field(asset.source, "host_name"), "Host does not exist."
                    )
                )
        if asset.tags is not None:
            for tag in asset.tags:
                try:
                    normalize_tag_name(tag)
                except ValueError as exc:
                    result.errors.append(
                        _issue(_with_field(asset.source, "tags"), str(exc))
                    )

    return result


def _issue(source, message: str) -> ImportIssue:
    location = source.location if source else "import"
    return ImportIssue(location=location, message=message)


def _with_field(source, field: str):
    if source is None:
        return None
    return type(source)(location=f"{source.location}.{field}")


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_valid_asset_type(value: str) -> bool:
    try:
        IPAssetType.normalize(value)
    except ValueError:
        return False
    return True
