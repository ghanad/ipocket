from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app import repository
from app.dependencies import get_connection
from app.utils import validate_ip_address

from .dependencies import require_editor
from .schemas import IPAssetCreate, IPAssetUpdate
from .utils import asset_payload, is_auto_host_for_bmc_enabled, normalize_asset_type_value

router = APIRouter()


@router.post("/ip-assets")
def create_ip_asset(
    payload: IPAssetCreate,
    connection=Depends(get_connection),
    user=Depends(require_editor),
):
    validate_ip_address(payload.ip_address)
    if payload.host_id is not None and repository.get_host_by_id(connection, payload.host_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Host not found.")
    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=payload.ip_address,
            asset_type=payload.type,
            project_id=payload.project_id,
            notes=payload.notes,
            host_id=payload.host_id,
            tags=payload.tags,
            auto_host_for_bmc=is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IP address already exists.",
        ) from exc
    tag_map = repository.list_tags_for_ip_assets(connection, [asset.id])
    return asset_payload(asset, tags=tag_map.get(asset.id, []))


@router.get("/ip-assets")
def list_ip_assets(
    project_id: Optional[int] = None,
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    normalized_asset_type = normalize_asset_type_value(asset_type) if asset_type is not None else None
    assets = repository.list_active_ip_assets(
        connection,
        project_id=project_id,
        asset_type=normalized_asset_type,
        unassigned_only=unassigned_only,
    )
    tag_map = repository.list_tags_for_ip_assets(connection, [asset.id for asset in assets])
    return [asset_payload(asset, tags=tag_map.get(asset.id, [])) for asset in assets]


@router.get("/ip-assets/{ip_address}")
def get_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
):
    asset = repository.get_ip_asset_by_ip(connection, ip_address)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    tag_map = repository.list_tags_for_ip_assets(connection, [asset.id])
    return asset_payload(asset, tags=tag_map.get(asset.id, []))


@router.patch("/ip-assets/{ip_address}")
def update_ip_asset(
    ip_address: str,
    payload: IPAssetUpdate,
    connection=Depends(get_connection),
    user=Depends(require_editor),
):
    if payload.host_id is not None and repository.get_host_by_id(connection, payload.host_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Host not found.")
    updated = repository.update_ip_asset(
        connection,
        ip_address=ip_address,
        asset_type=payload.type,
        project_id=payload.project_id,
        project_id_provided="project_id" in payload.model_fields_set,
        notes=payload.notes,
        host_id=payload.host_id,
        host_id_provided="host_id" in payload.model_fields_set,
        tags=payload.tags,
        current_user=user,
        notes_provided="notes" in payload.model_fields_set,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    tag_map = repository.list_tags_for_ip_assets(connection, [updated.id])
    return asset_payload(updated, tags=tag_map.get(updated.id, []))


@router.delete("/ip-assets/{ip_address}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
    user=Depends(require_editor),
):
    deleted = repository.delete_ip_asset(connection, ip_address, current_user=user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ip-assets/{ip_address}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    asset = repository.get_ip_asset_by_ip(connection, ip_address)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    repository.archive_ip_asset(connection, ip_address)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
