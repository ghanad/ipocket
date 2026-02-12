from __future__ import annotations

import os
import sqlite3
from typing import Optional

from fastapi import HTTPException

from app import repository
from app.models import IPAsset, IPAssetType
from app.utils import validate_ip_address


def _is_auto_host_for_bmc_enabled() -> bool:
    return os.getenv("IPOCKET_AUTO_HOST_FOR_BMC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _is_unassigned(project_id: Optional[int]) -> bool:
    return project_id is None


def _collect_inline_ip_errors(
    connection: sqlite3.Connection,
    host_id: Optional[int],
    os_ips: list[str],
    bmc_ips: list[str],
) -> tuple[list[str], list[tuple[str, IPAssetType]], list[tuple[str, IPAssetType]]]:
    errors: list[str] = []
    to_create: list[tuple[str, IPAssetType]] = []
    to_update: list[tuple[str, IPAssetType]] = []
    conflict_ips = set(os_ips) & set(bmc_ips)
    if conflict_ips:
        for ip in sorted(conflict_ips):
            errors.append(f"IP address appears in both OS and BMC fields: {ip}.")
    os_queue = [ip for ip in os_ips if ip not in conflict_ips]
    bmc_queue = [ip for ip in bmc_ips if ip not in conflict_ips]
    for ip_address, asset_type in [
        *[(ip, IPAssetType.OS) for ip in os_queue],
        *[(ip, IPAssetType.BMC) for ip in bmc_queue],
    ]:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(f"{exc.detail} ({ip_address})")
            continue
        existing = repository.get_ip_asset_by_ip(connection, ip_address)
        if existing is not None:
            if (
                host_id is not None
                and existing.host_id == host_id
                and existing.asset_type == asset_type
            ):
                continue
            to_update.append((ip_address, asset_type))
            continue
        to_create.append((ip_address, asset_type))
    deduped_errors = list(dict.fromkeys(errors))
    return deduped_errors, to_create, to_update


def _build_asset_view_models(
    assets: list[IPAsset],
    project_lookup: dict[int, dict[str, Optional[str]]],
    host_lookup: dict[int, str],
    tag_lookup: dict[int, list[dict[str, str]]],
    host_pair_lookup: Optional[dict[int, dict[str, list[str]]]] = None,
) -> list[dict]:
    view_models = []
    host_pair_lookup = host_pair_lookup or {}
    for asset in assets:
        project = project_lookup.get(asset.project_id) if asset.project_id else None
        project_name = project.get("name") if project else ""
        project_color = project.get("color") if project else None
        project_unassigned = not project_name
        host_name = host_lookup.get(asset.host_id) if asset.host_id else ""
        tags = tag_lookup.get(asset.id, [])
        tags_value = ", ".join(tag["name"] for tag in tags)
        host_pair = ""
        if asset.host_id and asset.asset_type in (IPAssetType.OS, IPAssetType.BMC):
            pair_type = (
                IPAssetType.BMC.value
                if asset.asset_type == IPAssetType.OS
                else IPAssetType.OS.value
            )
            pair_ips = host_pair_lookup.get(asset.host_id, {}).get(pair_type, [])
            host_pair = ", ".join(pair_ips)
        view_models.append(
            {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "type": asset.asset_type.value,
                "project_id": asset.project_id or "",
                "project_name": project_name,
                "project_color": project_color,
                "host_id": asset.host_id or "",
                "notes": asset.notes or "",
                "host_name": host_name,
                "tags": tags,
                "tags_value": tags_value,
                "host_pair": host_pair,
                "unassigned": _is_unassigned(asset.project_id),
                "project_unassigned": project_unassigned,
            }
        )
    return view_models
