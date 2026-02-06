from __future__ import annotations

import ipaddress
import re

from fastapi import HTTPException, status


def validate_ip_address(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid IP address."
        ) from exc


DEFAULT_PROJECT_COLOR = "#94a3b8"

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def normalize_hex_color(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not _HEX_COLOR_PATTERN.match(stripped):
        raise ValueError("Color must be a hex value like #1a2b3c.")
    return stripped.lower()
