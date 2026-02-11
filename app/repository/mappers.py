from __future__ import annotations

import ipaddress
import sqlite3

from app.models import (
    AuditLog,
    Host,
    IPAsset,
    IPAssetType,
    IPRange,
    Project,
    Tag,
    User,
    UserRole,
    Vendor,
)


def _row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
    )


def _row_to_host(row: sqlite3.Row) -> Host:
    return Host(
        id=row["id"], name=row["name"], notes=row["notes"], vendor=row["vendor_name"]
    )


def _row_to_vendor(row: sqlite3.Row) -> Vendor:
    return Vendor(id=row["id"], name=row["name"])


def _row_to_tag(row: sqlite3.Row) -> Tag:
    return Tag(id=row["id"], name=row["name"], color=row["color"])


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        hashed_password=row["hashed_password"],
        role=UserRole(row["role"]),
        is_active=bool(row["is_active"]),
    )


def _row_to_ip_asset(row: sqlite3.Row) -> IPAsset:
    return IPAsset(
        id=row["id"],
        ip_address=row["ip_address"],
        asset_type=IPAssetType(row["type"]),
        project_id=row["project_id"],
        host_id=row["host_id"],
        notes=row["notes"],
        archived=bool(row["archived"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _ip_address_sort_key(value: str) -> tuple[int, int, int | str]:
    try:
        parsed_ip = ipaddress.ip_address(value)
    except ValueError:
        parts = value.split(".")
        if len(parts) == 4 and all(part.isdigit() for part in parts):
            octets = [int(part) for part in parts]
            if all(0 <= octet <= 255 for octet in octets):
                packed_value = (
                    (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
                )
                return (0, 4, packed_value)
        return (1, 0, value.lower())
    return (0, parsed_ip.version, int(parsed_ip))


def _row_to_audit_log(row: sqlite3.Row) -> AuditLog:
    return AuditLog(
        id=row["id"],
        user_id=row["user_id"],
        username=row["username"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        target_label=row["target_label"],
        action=row["action"],
        changes=row["changes"],
        created_at=row["created_at"],
    )


def _row_to_ip_range(row: sqlite3.Row) -> IPRange:
    return IPRange(
        id=row["id"],
        name=row["name"],
        cidr=row["cidr"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
