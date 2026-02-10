from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, status

from app.imports.models import ImportApplyResult, ImportSummary
from app.models import Host, IPAsset, IPAssetType


def is_auto_host_for_bmc_enabled() -> bool:
    return os.getenv("IPOCKET_AUTO_HOST_FOR_BMC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def host_payload(host: Host) -> dict:
    return {"id": host.id, "name": host.name, "notes": host.notes, "vendor": host.vendor}


def asset_payload(asset: IPAsset, tags: Optional[list[str]] = None) -> dict:
    return {
        "id": asset.id,
        "ip_address": asset.ip_address,
        "type": asset.asset_type.value,
        "project_id": asset.project_id,
        "notes": asset.notes,
        "host_id": asset.host_id,
        "archived": asset.archived,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "tags": tags or [],
    }


def metrics_payload(metrics: dict[str, int]) -> str:
    return "\n".join(
        [
            f"ipam_ip_total {metrics['total']}",
            f"ipam_ip_archived_total {metrics['archived_total']}",
            f"ipam_ip_unassigned_project_total {metrics['unassigned_project_total']}",
            f"ipam_ip_unassigned_owner_total {metrics['unassigned_owner_total']}",
            f"ipam_ip_unassigned_both_total {metrics['unassigned_both_total']}",
            "",
        ]
    )


def summary_payload(summary: ImportSummary) -> dict[str, dict[str, int]]:
    return {
        "vendors": summary.vendors.__dict__,
        "projects": summary.projects.__dict__,
        "hosts": summary.hosts.__dict__,
        "ip_assets": summary.ip_assets.__dict__,
        "total": summary.total().__dict__,
    }


def import_result_payload(result: ImportApplyResult) -> dict[str, object]:
    return {
        "summary": summary_payload(result.summary),
        "errors": [issue.__dict__ for issue in result.errors],
        "warnings": [issue.__dict__ for issue in result.warnings],
    }


def normalize_asset_type_value(value: str) -> IPAssetType:
    try:
        return IPAssetType.normalize(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid asset type. Use VM, OS, BMC (formerly IPMI/iLO), VIP, OTHER.",
        ) from exc


def expand_csv_query_values(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    expanded: list[str] = []
    for value in values:
        for part in value.split(","):
            clean = part.strip()
            if clean:
                expanded.append(clean)
    return expanded


def require_sd_token_if_configured(sd_token: Optional[str], expected_token: Optional[str]) -> None:
    if not expected_token:
        return
    if sd_token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
