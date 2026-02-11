from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator

from app.models import IPAssetType
from app.utils import normalize_cidr, normalize_hex_color, normalize_tag_names, split_tag_string


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IPAssetCreate(BaseModel):
    ip_address: str
    type: IPAssetType
    project_id: Optional[int] = None
    notes: Optional[str] = None
    host_id: Optional[int] = None
    tags: Optional[list[str]] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_asset_type(cls, value):
        return IPAssetType.normalize(value)

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return split_tag_string(value)
        if isinstance(value, list):
            return value
        raise ValueError("Tags must be a list or comma-separated string.")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value):
        if value is None:
            return None
        return normalize_tag_names([str(item) for item in value])


class IPAssetUpdate(BaseModel):
    type: Optional[IPAssetType] = None
    project_id: Optional[int] = None
    notes: Optional[str] = None
    host_id: Optional[int] = None
    tags: Optional[list[str]] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_asset_type(cls, value):
        if value is None:
            return None
        return IPAssetType.normalize(value)

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return split_tag_string(value)
        if isinstance(value, list):
            return value
        raise ValueError("Tags must be a list or comma-separated string.")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value):
        if value is None:
            return None
        return normalize_tag_names([str(item) for item in value])


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_hex_color(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: Optional[str]) -> Optional[str]:
        try:
            return normalize_hex_color(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class HostCreate(BaseModel):
    name: str
    notes: Optional[str] = None
    vendor_id: Optional[int] = None


class HostUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    vendor_id: Optional[int] = None


class VendorCreate(BaseModel):
    name: str


class VendorUpdate(BaseModel):
    name: str


class IPRangeCreate(BaseModel):
    name: str
    cidr: str
    notes: Optional[str] = None

    @field_validator("cidr")
    @classmethod
    def normalize_cidr_value(cls, value: str) -> str:
        return normalize_cidr(value)
