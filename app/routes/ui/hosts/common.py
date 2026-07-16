from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status

from app import repository
from app.models import UserRole
from app.routes.ui._utils.assets import _build_asset_view_models
from app.routes.ui.utils import get_current_ui_user


_ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


def normalize_per_page(value: int, default: int = 20) -> int:
    if value not in _ALLOWED_PAGE_SIZES:
        return default
    return value


def empty_host_form_state() -> dict[str, Any]:
    return {
        "name": "",
        "notes": "",
        "vendor_id": "",
        "os_ips": "",
        "bmc_ips": "",
    }


def build_host_detail_payload(connection, host_id: int) -> dict[str, Any] | None:
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        return None

    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    linked_assets = [*grouped["os"], *grouped["bmc"], *grouped["other"]]
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in repository.list_projects(connection)
    }
    tag_lookup = repository.list_tag_details_for_ip_assets(
        connection, [asset.id for asset in linked_assets]
    )
    view_models = _build_asset_view_models(
        linked_assets,
        project_lookup,
        {host.id: host.name},
        tag_lookup,
    )
    by_id = {asset["id"]: asset for asset in view_models}

    def group_payload(name: str) -> list[dict[str, Any]]:
        return [
            {
                "id": by_id[asset.id]["id"],
                "ip_address": by_id[asset.id]["ip_address"],
                "type": by_id[asset.id]["type"],
                "project": (
                    None
                    if by_id[asset.id]["project_unassigned"]
                    else {
                        "name": by_id[asset.id]["project_name"],
                        "color": by_id[asset.id]["project_color"],
                    }
                ),
                "tags": by_id[asset.id]["tags"],
                "notes": by_id[asset.id]["notes"] or "—",
            }
            for asset in grouped[name]
        ]

    groups = {
        "os": group_payload("os"),
        "bmc": group_payload("bmc"),
        "other": group_payload("other"),
    }
    os_count = len(groups["os"])
    bmc_count = len(groups["bmc"])
    other_count = len(groups["other"])
    return {
        "host": {
            "id": host.id,
            "name": host.name,
            "vendor": host.vendor or "Unassigned",
            "notes": host.notes or "No notes",
        },
        "summary": {
            "linked_count": os_count + bmc_count + other_count,
            "os_count": os_count,
            "bmc_count": bmc_count,
            "other_count": other_count,
        },
        "groups": groups,
    }


def require_ui_host_writer(user=Depends(get_current_ui_user)):
    if user.role not in {UserRole.EDITOR, UserRole.SUPERUSER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
