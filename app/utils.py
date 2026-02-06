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


def normalize_cidr(value: str) -> str:
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise ValueError("CIDR must be a valid IPv4 network.") from exc
    if network.version != 4:
        raise ValueError("CIDR must be a valid IPv4 network.")
    return network.with_prefixlen


def parse_ipv4_network(value: str) -> ipaddress.IPv4Network:
    network = ipaddress.ip_network(value, strict=False)
    if network.version != 4:
        raise ValueError("CIDR must be a valid IPv4 network.")
    return network


DEFAULT_PROJECT_COLOR = "#94a3b8"
DEFAULT_TAG_COLOR = "#e2e8f0"

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_TAG_PATTERN = re.compile(r"^[a-z0-9_-]+$")


def normalize_hex_color(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not _HEX_COLOR_PATTERN.match(stripped):
        raise ValueError("Color must be a hex value like #1a2b3c.")
    return stripped.lower()


def split_tag_string(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def normalize_tag_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Tag name is required.")
    if not _TAG_PATTERN.match(normalized):
        raise ValueError("Tag name may include letters, digits, dash, and underscore only.")
    return normalized


def normalize_tag_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized_tags: list[str] = []
    for value in values:
        normalized = normalize_tag_name(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_tags.append(normalized)
    return normalized_tags
