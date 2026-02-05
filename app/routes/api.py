from __future__ import annotations

import os
import sqlite3
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from app import auth, build_info, repository
from app.dependencies import get_connection
from app.models import Host, IPAsset, IPAssetType, UserRole
from app.utils import validate_ip_address

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IPAssetCreate(BaseModel):
    ip_address: str
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    asset_type: IPAssetType = Field(alias="type")
    project_id: Optional[int] = None
    notes: Optional[str] = None
    host_id: Optional[int] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_asset_type(cls, value):
        return IPAssetType.normalize(value)


class IPAssetUpdate(BaseModel):
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    asset_type: Optional[IPAssetType] = Field(default=None, alias="type")
    project_id: Optional[int] = None
    notes: Optional[str] = None
    host_id: Optional[int] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_asset_type(cls, value):
        if value is None:
            return None
        return IPAssetType.normalize(value)


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class HostCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class HostUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


def _host_payload(host: Host) -> dict:
    return {"id": host.id, "name": host.name, "notes": host.notes}


def _asset_payload(asset: IPAsset) -> dict:
    return {
        "id": asset.id,
        "ip_address": asset.ip_address,
        "subnet": asset.subnet,
        "gateway": asset.gateway,
        "type": asset.asset_type.value,
        "project_id": asset.project_id,
        "notes": asset.notes,
        "host_id": asset.host_id,
        "archived": asset.archived,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def _metrics_payload(metrics: dict[str, int]) -> str:
    return "\n".join(
        [
            f"ipam_ip_total {metrics['total']}",
            f"ipam_ip_archived_total {metrics['archived_total']}",
            f"ipam_ip_unassigned_project_total {metrics['unassigned_project_total']}",
            "",
        ]
    )



def _normalize_asset_type_value(value: str) -> IPAssetType:
    try:
        return IPAssetType.normalize(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid asset type. Use VM, OS, BMC (formerly IPMI/iLO), VIP, OTHER.",
        ) from exc


def _expand_csv_query_values(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    expanded: list[str] = []
    for value in values:
        for part in value.split(","):
            clean = part.strip()
            if clean:
                expanded.append(clean)
    return expanded

def _require_sd_token_if_configured(sd_token: Optional[str], expected_token: Optional[str]) -> None:
    if not expected_token:
        return
    if sd_token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = auth.get_user_id_for_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = repository.get_user_by_id(connection, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_editor(user=Depends(get_current_user)):
    if user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


@router.get("/health")
def health_check() -> Response:
    return JSONResponse(content=build_info.get_build_info())


@router.get("/metrics")
def metrics(connection=Depends(get_connection)) -> Response:
    metrics_payload = repository.get_ip_asset_metrics(connection)
    return Response(content=_metrics_payload(metrics_payload), media_type="text/plain")


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
    _require_sd_token_if_configured(sd_token, os.getenv("IPOCKET_SD_TOKEN"))
    normalized_types = [
        _normalize_asset_type_value(value)
        for value in _expand_csv_query_values(asset_type)
    ]
    return repository.list_sd_targets(
        connection,
        port=port,
        only_assigned=only_assigned,
        project_names=_expand_csv_query_values(project),
        asset_types=normalized_types,
        group_by=group_by,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, connection=Depends(get_connection)) -> TokenResponse:
    user = repository.get_user_by_username(connection, request.username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not auth.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = auth.create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/ip-assets")
def create_ip_asset(
    payload: IPAssetCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    validate_ip_address(payload.ip_address)
    if payload.host_id is not None and repository.get_host_by_id(connection, payload.host_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Host not found.")
    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=payload.ip_address,
            subnet=payload.subnet,
            gateway=payload.gateway,
            asset_type=payload.asset_type,
            project_id=payload.project_id,
            notes=payload.notes,
            host_id=payload.host_id,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IP address already exists.",
        ) from exc
    return _asset_payload(asset)


@router.get("/ip-assets")
def list_ip_assets(
    project_id: Optional[int] = None,
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    normalized_asset_type = (
        _normalize_asset_type_value(asset_type) if asset_type is not None else None
    )
    assets = repository.list_active_ip_assets(
        connection,
        project_id=project_id,
        asset_type=normalized_asset_type,
        unassigned_only=unassigned_only,
    )
    return [_asset_payload(asset) for asset in assets]


@router.get("/ip-assets/{ip_address}")
def get_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
):
    asset = repository.get_ip_asset_by_ip(connection, ip_address)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _asset_payload(asset)


@router.patch("/ip-assets/{ip_address}")
def update_ip_asset(
    ip_address: str,
    payload: IPAssetUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    if payload.host_id is not None and repository.get_host_by_id(connection, payload.host_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Host not found.")
    updated = repository.update_ip_asset(
        connection,
        ip_address=ip_address,
        subnet=payload.subnet,
        gateway=payload.gateway,
        asset_type=payload.asset_type,
        project_id=payload.project_id,
        notes=payload.notes,
        host_id=payload.host_id,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _asset_payload(updated)


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


@router.post("/projects")
def create_project(
    payload: ProjectCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    project = repository.create_project(
        connection, name=payload.name, description=payload.description
    )
    return {"id": project.id, "name": project.name, "description": project.description}


@router.get("/projects")
def list_projects(connection=Depends(get_connection)):
    projects = repository.list_projects(connection)
    return [
        {"id": project.id, "name": project.name, "description": project.description}
        for project in projects
    ]


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    project = repository.update_project(
        connection,
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": project.id, "name": project.name, "description": project.description}


@router.get("/hosts")
def list_hosts(connection=Depends(get_connection)):
    hosts = repository.list_hosts(connection)
    return [_host_payload(host) for host in hosts]


@router.post("/hosts")
def create_host(
    payload: HostCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    host = repository.create_host(connection, name=payload.name, notes=payload.notes)
    return _host_payload(host)


@router.get("/hosts/{host_id}")
def get_host(host_id: int, connection=Depends(get_connection)):
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    return {
        **_host_payload(host),
        "linked_assets": {
            "os": [_asset_payload(asset) for asset in grouped["os"]],
            "bmc": [_asset_payload(asset) for asset in grouped["bmc"]],
            "other": [_asset_payload(asset) for asset in grouped["other"]],
        },
    }


@router.patch("/hosts/{host_id}")
def update_host(
    host_id: int,
    payload: HostUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    host = repository.update_host(connection, host_id=host_id, name=payload.name, notes=payload.notes)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _host_payload(host)
