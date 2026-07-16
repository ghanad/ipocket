from __future__ import annotations

from fastapi import HTTPException, status

from app import repository
from app.models import IPAssetType, User, UserRole
from app.routes.ui.utils import (
    _build_asset_view_models,
    _is_auto_host_for_bmc_enabled,
    _normalize_asset_type,
    _parse_optional_str,
)

from .helpers import (
    _delete_requires_exact_ip,
    _friendly_audit_changes,
    _parse_selected_tags,
)


def get_active_ip_asset(connection, asset_id: int):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return asset


def build_ip_asset_detail_payload(connection, asset_id: int, user: User) -> dict:
    asset = get_active_ip_asset(connection, asset_id)
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    tags = list(repository.list_tags(connection))
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in projects
    }
    host_lookup = {host.id: host.name for host in hosts}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id])
    view_model = _build_asset_view_models(
        [asset], project_lookup, host_lookup, tag_lookup
    )[0]
    view_model["host_pair_assets"] = []
    if asset.host_id and asset.asset_type in (IPAssetType.OS, IPAssetType.BMC):
        grouped = repository.get_host_linked_assets_grouped(connection, asset.host_id)
        pair_key = "bmc" if asset.asset_type == IPAssetType.OS else "os"
        view_model["host_pair_assets"] = [
            {"id": pair.id, "ip_address": pair.ip_address}
            for pair in grouped[pair_key]
        ]

    audit_logs = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": _friendly_audit_changes(log.changes or ""),
        }
        for log in repository.get_audit_logs_for_ip(connection, asset.id)
    ]
    tag_names = [tag["name"] for tag in view_model["tags"]]
    can_edit = user.role == UserRole.EDITOR
    auto_host_enabled = _is_auto_host_for_bmc_enabled()
    return {
        "asset": view_model,
        "audit_logs": audit_logs,
        "metadata": {
            "projects": [
                {"id": item.id, "name": item.name, "color": item.color}
                for item in projects
            ],
            "hosts": [{"id": item.id, "name": item.name} for item in hosts],
            "tags": [
                {"id": item.id, "name": item.name, "color": item.color}
                for item in tags
            ],
            "types": [item.value for item in IPAssetType],
        },
        "can_edit": can_edit,
        "delete_requires_exact_ip": _delete_requires_exact_ip(asset, tag_names),
        "auto_host_enabled": auto_host_enabled,
        "can_auto_host": bool(
            can_edit
            and auto_host_enabled
            and asset.asset_type == IPAssetType.BMC
            and asset.host_id is None
        ),
    }


def validate_ip_asset_update(
    connection,
    *,
    asset_type: str,
    project_id: int | None,
    host_id: int | None,
    raw_tags: list[str],
) -> tuple[IPAssetType, list[str]]:
    errors: list[str] = []
    normalized_type = None
    try:
        normalized_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_type is None and not errors:
        errors.append("Asset type is required.")
    if (
        project_id is not None
        and repository.get_project_by_id(connection, project_id) is None
    ):
        errors.append("Selected project does not exist.")
    if host_id is not None and repository.get_host_by_id(connection, host_id) is None:
        errors.append("Selected host does not exist.")
    if normalized_type not in (IPAssetType.OS, IPAssetType.BMC) and host_id is not None:
        errors.append("Host can only be assigned to OS or BMC assets.")
    tags, tag_errors = _parse_selected_tags(connection, raw_tags)
    errors.extend(tag_errors)
    if errors or normalized_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )
    return normalized_type, tags


def update_ip_asset_from_ui(
    connection,
    *,
    asset,
    asset_type: str,
    project_id: int | None,
    host_id: int | None,
    notes: str | None,
    raw_tags: list[str],
    user: User,
):
    normalized_type, tags = validate_ip_asset_update(
        connection,
        asset_type=asset_type,
        project_id=project_id,
        host_id=host_id,
        raw_tags=raw_tags,
    )
    return repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=normalized_type,
        project_id=project_id,
        project_id_provided=True,
        host_id=host_id,
        host_id_provided=True,
        notes=_parse_optional_str(notes),
        notes_provided=True,
        tags=tags,
        current_user=user,
    )


def auto_host_ip_asset(connection, *, asset, user: User):
    if not _is_auto_host_for_bmc_enabled():
        raise HTTPException(status_code=400, detail="Auto-host creation is disabled.")
    if asset.asset_type != IPAssetType.BMC:
        raise HTTPException(
            status_code=400,
            detail="Auto-host creation is only available for BMC assets.",
        )
    if asset.host_id is not None:
        raise HTTPException(
            status_code=409, detail="This IP is already assigned to a host."
        )
    host_name = f"server_{asset.ip_address}"
    host = repository.get_host_by_name(connection, host_name)
    if host is None:
        host = repository.create_host(connection, name=host_name, notes=None, vendor=None)
    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        host_id=host.id,
        host_id_provided=True,
        current_user=user,
    )
    return host


def validate_ip_asset_delete(
    connection, *, asset, acknowledged: bool, confirm_ip: str
) -> None:
    tag_names = repository.list_tags_for_ip_assets(connection, [asset.id]).get(
        asset.id, []
    )
    errors: list[str] = []
    if not acknowledged:
        errors.append("Confirm that this delete cannot be undone.")
    if _delete_requires_exact_ip(asset, tag_names) and confirm_ip.strip() != asset.ip_address:
        errors.append("Type the exact IP address to delete this high-risk asset.")
    if errors:
        raise HTTPException(status_code=400, detail=errors)
