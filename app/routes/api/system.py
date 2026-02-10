from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse, Response

from app import build_info, repository
from app.dependencies import get_connection

from .utils import (
    expand_csv_query_values,
    metrics_payload,
    normalize_asset_type_value,
    require_sd_token_if_configured,
)

router = APIRouter()


@router.get("/health")
def health_check() -> Response:
    return JSONResponse(content=build_info.get_build_info())


@router.get("/metrics")
def metrics(connection=Depends(get_connection)) -> Response:
    payload = repository.get_ip_asset_metrics(connection)
    return Response(content=metrics_payload(payload), media_type="text/plain")


@router.get("/sd/node")
def service_discovery_targets(
    port: int = Query(default=9100, ge=1, le=65535),
    only_assigned: bool = Query(default=False),
    project: Optional[list[str]] = Query(default=None),
    asset_type: Optional[list[str]] = Query(default=None, alias="type"),
    group_by: Literal["none", "project"] = Query(default="none"),
    sd_token: Optional[str] = Header(default=None, alias="X-SD-Token"),
    connection=Depends(get_connection),
):
    require_sd_token_if_configured(sd_token, os.getenv("IPOCKET_SD_TOKEN"))
    normalized_types = [
        normalize_asset_type_value(value)
        for value in expand_csv_query_values(asset_type)
    ]
    return repository.list_sd_targets(
        connection,
        port=port,
        only_assigned=only_assigned,
        project_names=expand_csv_query_values(project),
        asset_types=normalized_types,
        group_by=group_by,
    )
