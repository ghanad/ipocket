from __future__ import annotations

from fastapi import APIRouter

from . import assets, auth, hosts, imports, metadata, system
from .dependencies import get_current_user, require_editor
from .utils import (
    asset_payload,
    expand_csv_query_values,
    host_payload,
    is_auto_host_for_bmc_enabled,
    metrics_payload,
    normalize_asset_type_value,
    require_sd_token_if_configured,
)

router = APIRouter()
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(assets.router)
router.include_router(hosts.router)
router.include_router(metadata.router)
router.include_router(imports.router)

__all__ = [
    "router",
    "require_editor",
    "get_current_user",
    "asset_payload",
    "host_payload",
    "metrics_payload",
    "normalize_asset_type_value",
    "expand_csv_query_values",
    "require_sd_token_if_configured",
    "is_auto_host_for_bmc_enabled",
]
