from __future__ import annotations

import ipaddress

from fastapi import HTTPException, status


def validate_ip_address(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid IP address."
        ) from exc
