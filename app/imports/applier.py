from __future__ import annotations

from app import repository
from app.imports.models import (
    ImportApplyResult,
    ImportBundle,
    ImportIssue,
    ImportSummary,
)
from app.models import IPAssetType
from app.utils import normalize_tag_names


def apply_bundle(
    connection, bundle: ImportBundle, dry_run: bool = False
) -> ImportApplyResult:
    summary = ImportSummary()
    warnings: list[ImportIssue] = []

    vendor_id_map, vendor_updates = _upsert_vendors(
        connection, bundle, summary, dry_run=dry_run
    )
    project_id_map, project_updates = _upsert_projects(
        connection, bundle, summary, dry_run=dry_run
    )
    host_id_map, host_updates = _upsert_hosts(
        connection,
        bundle,
        vendor_id_map,
        summary,
        dry_run=dry_run,
    )
    _upsert_ip_assets(
        connection,
        bundle,
        project_id_map,
        host_id_map,
        summary,
        dry_run=dry_run,
    )

    if vendor_updates or project_updates or host_updates:
        warnings.append(
            ImportIssue(
                location="import",
                message="Some related records were updated based on import data.",
                level="warning",
            )
        )

    return ImportApplyResult(summary=summary, warnings=warnings)


def _upsert_vendors(
    connection, bundle: ImportBundle, summary: ImportSummary, dry_run: bool
) -> tuple[dict[str, int], bool]:
    existing = {vendor.name: vendor for vendor in repository.list_vendors(connection)}
    id_map = {name: vendor.id for name, vendor in existing.items()}
    updated_any = False
    temp_id = -1

    for vendor in bundle.vendors:
        name = vendor.name.strip()
        if not name:
            continue
        existing_vendor = existing.get(name)
        if existing_vendor:
            summary.vendors.would_skip += 1
            continue
        summary.vendors.would_create += 1
        if dry_run:
            id_map[name] = temp_id
            temp_id -= 1
            continue
        created = repository.create_vendor(connection, name)
        id_map[name] = created.id
    return id_map, updated_any


def _upsert_projects(
    connection, bundle: ImportBundle, summary: ImportSummary, dry_run: bool
) -> tuple[dict[str, int], bool]:
    existing = {
        project.name: project for project in repository.list_projects(connection)
    }
    id_map = {name: project.id for name, project in existing.items()}
    updated_any = False
    temp_id = -100

    for project in bundle.projects:
        name = project.name.strip()
        if not name:
            continue
        existing_project = existing.get(name)
        if existing_project is None:
            summary.projects.would_create += 1
            if dry_run:
                id_map[name] = temp_id
                temp_id -= 1
                continue
            created = repository.create_project(
                connection,
                name=name,
                description=project.description,
                color=project.color,
            )
            id_map[name] = created.id
            continue

        target_description = (
            project.description
            if project.description is not None
            else existing_project.description
        )
        target_color = (
            project.color if project.color is not None else existing_project.color
        )
        if (
            target_description == existing_project.description
            and target_color == existing_project.color
        ):
            summary.projects.would_skip += 1
            continue
        summary.projects.would_update += 1
        updated_any = True
        if dry_run:
            continue
        repository.update_project(
            connection,
            project_id=existing_project.id,
            name=name,
            description=project.description,
            color=project.color,
        )

    return id_map, updated_any


def _upsert_hosts(
    connection,
    bundle: ImportBundle,
    vendor_id_map: dict[str, int],
    summary: ImportSummary,
    dry_run: bool,
) -> tuple[dict[str, int], bool]:
    existing = {host.name: host for host in repository.list_hosts(connection)}
    id_map = {name: host.id for name, host in existing.items()}
    updated_any = False
    temp_id = -200

    vendor_lookup = {
        vendor.name: vendor for vendor in repository.list_vendors(connection)
    }

    for host in bundle.hosts:
        name = host.name.strip()
        if not name:
            continue
        existing_host = existing.get(name)
        vendor_name = host.vendor_name.strip() if host.vendor_name else None
        vendor_id = vendor_id_map.get(vendor_name) if vendor_name else None
        if vendor_name and vendor_id is None:
            vendor = vendor_lookup.get(vendor_name)
            vendor_id = vendor.id if vendor else None
        if existing_host is None:
            summary.hosts.would_create += 1
            if dry_run:
                id_map[name] = temp_id
                temp_id -= 1
                continue
            vendor_name_value = vendor_name if vendor_name else None
            created = repository.create_host(
                connection,
                name=name,
                notes=host.notes,
                vendor=vendor_name_value,
            )
            id_map[name] = created.id
            continue

        target_notes = host.notes if host.notes is not None else existing_host.notes
        target_vendor = vendor_name if vendor_name is not None else existing_host.vendor
        if (
            target_notes == existing_host.notes
            and target_vendor == existing_host.vendor
        ):
            summary.hosts.would_skip += 1
            continue
        summary.hosts.would_update += 1
        updated_any = True
        if dry_run:
            continue
        repository.update_host(
            connection,
            host_id=existing_host.id,
            name=name,
            notes=host.notes,
            vendor=vendor_name,
        )

    return id_map, updated_any


def _upsert_ip_assets(
    connection,
    bundle: ImportBundle,
    project_id_map: dict[str, int],
    host_id_map: dict[str, int],
    summary: ImportSummary,
    dry_run: bool,
) -> None:
    for asset in bundle.ip_assets:
        ip_address = asset.ip_address.strip()
        if not ip_address:
            continue
        existing = repository.get_ip_asset_by_ip(connection, ip_address)
        asset_type = IPAssetType.normalize(asset.asset_type)
        project_id = (
            project_id_map.get(asset.project_name) if asset.project_name else None
        )
        host_id = host_id_map.get(asset.host_name) if asset.host_name else None

        if existing is None:
            summary.ip_assets.would_create += 1
            if dry_run:
                continue
            created = repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                project_id=project_id,
                host_id=host_id,
                notes=asset.notes,
                tags=asset.tags,
            )
            if asset.archived is True:
                repository.set_ip_asset_archived(
                    connection, created.ip_address, archived=True
                )
            continue

        existing_tags = repository.list_tags_for_ip_assets(
            connection, [existing.id]
        ).get(existing.id, [])
        if asset.tags is None:
            target_tags = existing_tags
        elif asset.merge_tags:
            target_tags = normalize_tag_names([*existing_tags, *asset.tags])
        else:
            target_tags = normalize_tag_names(asset.tags)
        notes_should_update = asset.notes_provided or asset.notes is not None
        if notes_should_update and asset.preserve_existing_notes and existing.notes:
            notes_should_update = False
        target_notes = asset.notes if notes_should_update else existing.notes
        target_project_id = (
            project_id if asset.project_name is not None else existing.project_id
        )
        target_host_id = host_id if asset.host_name is not None else existing.host_id
        target_archived = (
            asset.archived if asset.archived is not None else existing.archived
        )

        if (
            target_notes == existing.notes
            and target_project_id == existing.project_id
            and target_host_id == existing.host_id
            and asset_type == existing.asset_type
            and bool(target_archived) == bool(existing.archived)
            and target_tags == existing_tags
        ):
            summary.ip_assets.would_skip += 1
            continue

        summary.ip_assets.would_update += 1
        if dry_run:
            continue

        repository.update_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=asset_type,
            project_id=project_id,
            host_id=host_id,
            notes=asset.notes,
            tags=target_tags,
            notes_provided=notes_should_update,
        )
        if asset.archived is not None:
            repository.set_ip_asset_archived(
                connection, ip_address, archived=asset.archived
            )
