from __future__ import annotations

from typing import Any


_ALLOWED_PAGE_SIZES = {10, 20, 50, 100}


def normalize_per_page(value: int, default: int = 20) -> int:
    if value not in _ALLOWED_PAGE_SIZES:
        return default
    return value


def empty_host_form_state() -> dict[str, Any]:
    return {
        "name": "",
        "notes": "",
        "vendor_id": "",
        "os_ips": "",
        "bmc_ips": "",
    }
