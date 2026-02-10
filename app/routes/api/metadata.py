from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import repository
from app.dependencies import get_connection

from .dependencies import require_editor
from .schemas import IPRangeCreate, ProjectCreate, ProjectUpdate, VendorCreate, VendorUpdate

router = APIRouter()


@router.post("/projects")
def create_project(
    payload: ProjectCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    project = repository.create_project(
        connection,
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
    }


@router.get("/projects")
def list_projects(connection=Depends(get_connection)):
    projects = repository.list_projects(connection)
    return [
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "color": project.color,
        }
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
        color=payload.color,
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
    }


@router.get("/ranges")
def list_ranges(connection=Depends(get_connection)):
    ranges = repository.list_ip_ranges(connection)
    return [
        {
            "id": ip_range.id,
            "name": ip_range.name,
            "cidr": ip_range.cidr,
            "notes": ip_range.notes,
            "created_at": ip_range.created_at,
            "updated_at": ip_range.updated_at,
        }
        for ip_range in ranges
    ]


@router.post("/ranges")
def create_range(
    payload: IPRangeCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    ip_range = repository.create_ip_range(
        connection,
        name=payload.name,
        cidr=payload.cidr,
        notes=payload.notes,
    )
    return {
        "id": ip_range.id,
        "name": ip_range.name,
        "cidr": ip_range.cidr,
        "notes": ip_range.notes,
        "created_at": ip_range.created_at,
        "updated_at": ip_range.updated_at,
    }


@router.get("/vendors")
def list_vendors(connection=Depends(get_connection)):
    vendors = repository.list_vendors(connection)
    return [{"id": vendor.id, "name": vendor.name} for vendor in vendors]


@router.post("/vendors")
def create_vendor(
    payload: VendorCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    vendor = repository.create_vendor(connection, payload.name.strip())
    return {"id": vendor.id, "name": vendor.name}


@router.patch("/vendors/{vendor_id}")
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    vendor = repository.update_vendor(connection, vendor_id, payload.name.strip())
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": vendor.id, "name": vendor.name}
