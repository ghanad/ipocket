from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app import repository
from app.dependencies import get_connection
from app.routes.api.schemas import UIIPAssetDelete, UIIPAssetWrite
from app.routes.ui.utils import get_current_ui_user, require_ui_editor

from .common import (
    auto_host_ip_asset,
    build_ip_asset_detail_payload,
    get_active_ip_asset,
    update_ip_asset_from_ui,
    validate_ip_asset_delete,
)

router = APIRouter()


@router.get("/api/ui/ip-assets/{asset_id}/detail")
def get_ip_asset_detail_for_ui(
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
):
    return build_ip_asset_detail_payload(connection, asset_id, user)


@router.patch("/api/ui/ip-assets/{asset_id}")
def update_ip_asset_for_ui(
    asset_id: int,
    payload: UIIPAssetWrite,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = get_active_ip_asset(connection, asset_id)
    update_ip_asset_from_ui(
        connection,
        asset=asset,
        asset_type=payload.type,
        project_id=payload.project_id,
        host_id=payload.host_id,
        notes=payload.notes,
        raw_tags=payload.tags,
        user=user,
    )
    return {"message": "IP asset updated.", "asset_id": asset.id}


@router.post("/api/ui/ip-assets/{asset_id}/auto-host")
def auto_host_ip_asset_for_ui(
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = get_active_ip_asset(connection, asset_id)
    host = auto_host_ip_asset(connection, asset=asset, user=user)
    return {"host_id": host.id, "host_name": host.name}


@router.delete("/api/ui/ip-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ip_asset_for_ui(
    asset_id: int,
    payload: UIIPAssetDelete,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> Response:
    asset = get_active_ip_asset(connection, asset_id)
    validate_ip_asset_delete(
        connection,
        asset=asset,
        acknowledged=payload.acknowledged,
        confirm_ip=payload.confirm_ip,
    )
    if not repository.delete_ip_asset(
        connection, asset.ip_address, current_user=user
    ):
        raise HTTPException(status_code=404)
    return Response(status_code=204)
