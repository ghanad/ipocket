from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app import repository
from app.dependencies import get_connection
from app.routes.api.schemas import (
    UIIPAssetBulkWrite,
    UIIPAssetCreate,
    UIIPAssetDelete,
    UIIPAssetWrite,
)
from app.routes.ui.utils import (
    get_current_ui_user,
    get_optional_current_ui_user,
    require_ui_editor,
)

from .common import (
    auto_host_ip_asset,
    bulk_update_ip_assets_from_ui,
    build_ip_asset_detail_payload,
    create_ip_asset_from_ui,
    get_active_ip_asset,
    update_ip_asset_from_ui,
    validate_ip_asset_delete,
)
from .listing import build_ip_asset_list_payload, normalize_ip_asset_list_query

router = APIRouter()


@router.get("/api/ui/ip-assets")
def list_ip_assets_for_ui(
    q: str | None = None,
    project_id: str | None = None,
    tag: list[str] | None = Query(default=None),
    tag_all: list[str] | None = Query(default=None),
    tag_any: list[str] | None = Query(default=None),
    tag_not: list[str] | None = Query(default=None),
    asset_type: str | None = Query(default=None, alias="type"),
    assigned_only: bool = Query(default=False, alias="assigned-only"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    archived_only: bool = Query(default=False, alias="archived-only"),
    page: str | None = None,
    per_page: str | None = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
    user=Depends(get_optional_current_ui_user),
):
    query = normalize_ip_asset_list_query(
        q=q,
        project_id=project_id,
        tag=tag,
        tag_all=tag_all,
        tag_any=tag_any,
        tag_not=tag_not,
        asset_type=asset_type,
        assigned_only=assigned_only,
        unassigned_only=unassigned_only,
        archived_only=archived_only,
        page=page,
        per_page=per_page,
    )
    return build_ip_asset_list_payload(connection, query, user)


@router.post(
    "/api/ui/ip-assets",
    status_code=status.HTTP_201_CREATED,
)
def create_ip_asset_for_ui(
    payload: UIIPAssetCreate,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = create_ip_asset_from_ui(
        connection,
        ip_address=payload.ip_address,
        asset_type=payload.type,
        project_id=payload.project_id,
        host_id=payload.host_id,
        notes=payload.notes,
        raw_tags=payload.tags,
        user=user,
    )
    return {
        "message": "IP asset created.",
        "asset_id": asset.id,
        "ip_address": asset.ip_address,
    }


@router.post("/api/ui/ip-assets/bulk")
def bulk_update_ip_assets_for_ui(
    payload: UIIPAssetBulkWrite,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    updated = bulk_update_ip_assets_from_ui(
        connection,
        asset_ids=payload.asset_ids,
        asset_type=payload.type,
        project_id=payload.project_id,
        set_project=payload.set_project,
        tags_to_add_raw=payload.tags_to_add,
        tags_to_remove_raw=payload.tags_to_remove,
        notes=payload.notes,
        notes_mode=payload.notes_mode,
        user=user,
    )
    return {
        "message": f"Updated {len(updated)} IP assets.",
        "updated_count": len(updated),
    }


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
