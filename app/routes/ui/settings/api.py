from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_session
from app.models import UserRole
from app.routes.ui.utils import get_current_ui_user, require_ui_editor
from app.utils import (
    DEFAULT_PROJECT_COLOR,
    DEFAULT_TAG_COLOR,
    normalize_hex_color,
    normalize_tag_name,
    suggest_random_tag_color,
)

from . import repository

router = APIRouter()


class ProjectInput(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name is required.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_hex_color(value)
        except ValueError as exc:
            raise ValueError(
                "Project color must be a valid hex color (example: #1a2b3c)."
            ) from exc


class VendorInput(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Vendor name is required.")
        return normalized


class TagInput(BaseModel):
    name: str
    color: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        try:
            return normalize_tag_name(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_hex_color(value)
        except ValueError as exc:
            raise ValueError(
                "Tag color must be a valid hex color (example: #1a2b3c)."
            ) from exc


class DeleteInput(BaseModel):
    confirm_name: str


def _can_edit(user) -> bool:
    return user.role == UserRole.EDITOR


def _project_payload(project, usage_count: int = 0) -> dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
        "usage_count": usage_count,
    }


def _vendor_payload(vendor, usage_count: int = 0) -> dict[str, object]:
    return {"id": vendor.id, "name": vendor.name, "usage_count": usage_count}


def _tag_payload(tag, usage_count: int = 0) -> dict[str, object]:
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "usage_count": usage_count,
    }


@router.get("/api/ui/library/projects")
def list_projects_for_ui(
    session=Depends(get_session),
    user=Depends(get_current_ui_user),
):
    counts = repository.list_project_ip_counts(session)
    return {
        "items": [
            _project_payload(project, counts.get(project.id, 0))
            for project in repository.list_projects(session)
        ],
        "can_edit": _can_edit(user),
        "default_color": DEFAULT_PROJECT_COLOR,
    }


@router.post("/api/ui/library/projects", status_code=status.HTTP_201_CREATED)
def create_project_for_ui(
    payload: ProjectInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    try:
        project = repository.create_project(
            session,
            name=payload.name,
            description=payload.description,
            color=payload.color or DEFAULT_PROJECT_COLOR,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists.",
        ) from exc
    return _project_payload(project)


@router.patch("/api/ui/library/projects/{project_id}")
def update_project_for_ui(
    project_id: int,
    payload: ProjectInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    if repository.get_project_by_id(session, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        project = repository.update_project(
            session,
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            color=payload.color or DEFAULT_PROJECT_COLOR,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists.",
        ) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return _project_payload(project)


@router.delete(
    "/api/ui/library/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_for_ui(
    project_id: int,
    payload: DeleteInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> Response:
    project = repository.get_project_by_id(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if payload.confirm_name.strip() != project.name:
        raise HTTPException(
            status_code=400,
            detail="Project name confirmation does not match.",
        )
    if not repository.delete_project(session, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/ui/library/vendors")
def list_vendors_for_ui(
    session=Depends(get_session),
    user=Depends(get_current_ui_user),
):
    counts = repository.list_vendor_ip_counts(session)
    return {
        "items": [
            _vendor_payload(vendor, counts.get(vendor.id, 0))
            for vendor in repository.list_vendors(session)
        ],
        "can_edit": _can_edit(user),
    }


@router.post("/api/ui/library/vendors", status_code=status.HTTP_201_CREATED)
def create_vendor_for_ui(
    payload: VendorInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    try:
        vendor = repository.create_vendor(session, name=payload.name)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor name already exists.",
        ) from exc
    return _vendor_payload(vendor)


@router.patch("/api/ui/library/vendors/{vendor_id}")
def update_vendor_for_ui(
    vendor_id: int,
    payload: VendorInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    if repository.get_vendor_by_id(session, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    try:
        vendor = repository.update_vendor(session, vendor_id, payload.name)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor name already exists.",
        ) from exc
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return _vendor_payload(vendor)


@router.delete(
    "/api/ui/library/vendors/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_vendor_for_ui(
    vendor_id: int,
    payload: DeleteInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> Response:
    vendor = repository.get_vendor_by_id(session, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    if payload.confirm_name.strip() != vendor.name:
        raise HTTPException(
            status_code=400,
            detail="Vendor name confirmation does not match.",
        )
    if not repository.delete_vendor(session, vendor_id):
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/ui/library/tags")
def list_tags_for_ui(
    session=Depends(get_session),
    user=Depends(get_current_ui_user),
):
    counts = repository.list_tag_ip_counts(session)
    return {
        "items": [
            _tag_payload(tag, counts.get(tag.id, 0))
            for tag in repository.list_tags(session)
        ],
        "can_edit": _can_edit(user),
        "suggested_color": suggest_random_tag_color(),
        "default_color": DEFAULT_TAG_COLOR,
    }


@router.post("/api/ui/library/tags", status_code=status.HTTP_201_CREATED)
def create_tag_for_ui(
    payload: TagInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    try:
        tag = repository.create_tag(
            session,
            name=payload.name,
            color=payload.color or suggest_random_tag_color(),
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tag name already exists.",
        ) from exc
    return _tag_payload(tag)


@router.patch("/api/ui/library/tags/{tag_id}")
def update_tag_for_ui(
    tag_id: int,
    payload: TagInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
):
    if repository.get_tag_by_id(session, tag_id) is None:
        raise HTTPException(status_code=404, detail="Tag not found.")
    try:
        tag = repository.update_tag(
            session,
            tag_id,
            payload.name,
            payload.color or DEFAULT_TAG_COLOR,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tag name already exists.",
        ) from exc
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found.")
    return _tag_payload(tag)


@router.delete(
    "/api/ui/library/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_tag_for_ui(
    tag_id: int,
    payload: DeleteInput,
    session=Depends(get_session),
    _user=Depends(require_ui_editor),
) -> Response:
    tag = repository.get_tag_by_id(session, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found.")
    if payload.confirm_name.strip() != tag.name:
        raise HTTPException(
            status_code=400,
            detail="Tag name confirmation does not match.",
        )
    if not repository.delete_tag(session, tag_id):
        raise HTTPException(status_code=404, detail="Tag not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
