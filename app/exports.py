from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app import repository
from app.models import IPAssetType


def export_vendors(connection) -> list[dict[str, object]]:
    vendors = repository.list_vendors(connection)
    return [{"name": vendor.name} for vendor in vendors]


def export_projects(connection, project_name: Optional[str] = None) -> list[dict[str, object]]:
    projects = repository.list_projects(connection)
    if project_name:
        projects = [project for project in projects if project.name == project_name]
    return [
        {"name": project.name, "description": project.description, "color": project.color}
        for project in projects
    ]


def export_hosts(connection, host_name: Optional[str] = None) -> list[dict[str, object]]:
    hosts = repository.list_hosts(connection)
    if host_name:
        hosts = [host for host in hosts if host.name == host_name]
    return [
        {"name": host.name, "notes": host.notes, "vendor_name": host.vendor}
        for host in hosts
    ]


def export_ip_assets(
    connection,
    include_archived: bool = False,
    asset_type: Optional[IPAssetType] = None,
    project_name: Optional[str] = None,
    host_name: Optional[str] = None,
) -> list[dict[str, object]]:
    return repository.list_ip_assets_for_export(
        connection,
        include_archived=include_archived,
        asset_type=asset_type,
        project_name=project_name,
        host_name=host_name,
    )


def export_bundle(
    connection,
    include_archived: bool = False,
    asset_type: Optional[IPAssetType] = None,
    project_name: Optional[str] = None,
    host_name: Optional[str] = None,
) -> dict[str, object]:
    exported_at = datetime.now(timezone.utc).isoformat()
    return {
        "app": "ipocket",
        "schema_version": "1",
        "exported_at": exported_at,
        "data": {
            "vendors": export_vendors(connection),
            "projects": export_projects(connection, project_name=project_name),
            "hosts": export_hosts(connection, host_name=host_name),
            "ip_assets": export_ip_assets(
                connection,
                include_archived=include_archived,
                asset_type=asset_type,
                project_name=project_name,
                host_name=host_name,
            ),
        },
    }
