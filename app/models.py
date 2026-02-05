from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IPAssetType(str, Enum):
    OS = "OS"
    BMC = "BMC"
    VM = "VM"
    VIP = "VIP"
    OTHER = "OTHER"

    @classmethod
    def normalize(cls, value: "IPAssetType | str") -> "IPAssetType":
        if isinstance(value, cls):
            return value
        if value in {"IPMI_ILO", "IPMI_iLO"}:
            return cls.BMC
        return cls(value)


class UserRole(str, Enum):
    VIEWER = "Viewer"
    EDITOR = "Editor"
    ADMIN = "Admin"


@dataclass
class Project:
    id: int
    name: str
    description: Optional[str]


@dataclass
class Host:
    id: int
    name: str
    notes: Optional[str]
    vendor: Optional[str]


@dataclass
class Vendor:
    id: int
    name: str


@dataclass
class User:
    id: int
    username: str
    hashed_password: str
    role: UserRole
    is_active: bool


@dataclass
class IPAsset:
    id: int
    ip_address: str
    subnet: str
    gateway: str
    asset_type: IPAssetType
    project_id: Optional[int]
    host_id: Optional[int]
    notes: Optional[str]
    archived: bool
    created_at: str
    updated_at: str
