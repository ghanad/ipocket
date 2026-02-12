from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException, status

from app.models import IPAssetType
from app.utils import normalize_hex_color


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _parse_optional_int_query(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _parse_positive_int_query(value: Optional[str], default: int) -> int:
    parsed = _parse_optional_int_query(value)
    if parsed is None or parsed <= 0:
        return default
    return parsed


def _parse_inline_ip_list(value: Optional[str]) -> list[str]:
    normalized = _parse_optional_str(value)
    if normalized is None:
        return []
    parts = re.split(r"[,\s]+", normalized)
    seen: set[str] = set()
    entries: list[str] = []
    for part in parts:
        candidate = part.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        entries.append(candidate)
    return entries


def _normalize_project_color(value: Optional[str]) -> Optional[str]:
    normalized_value = _parse_optional_str(value)
    if normalized_value is None:
        return None
    return normalize_hex_color(normalized_value)


def _normalize_asset_type(value: Optional[str]) -> Optional[IPAssetType]:
    normalized_value = _parse_optional_str(value)
    if normalized_value is None:
        return None
    return IPAssetType.normalize(normalized_value)


def _normalize_export_asset_type(value: Optional[str]) -> Optional[IPAssetType]:
    if value is None:
        return None
    try:
        return IPAssetType.normalize(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid asset type. Use VM, OS, BMC (formerly IPMI/iLO), VIP, OTHER.",
        ) from exc
