from __future__ import annotations

import os
from pathlib import Path

_FALSE_VALUES = {"0", "false", "no", "off"}


def use_local_assets() -> bool:
    override = os.getenv("IPOCKET_DOCKER_ASSETS")
    if override is not None:
        return override.strip().lower() not in _FALSE_VALUES
    return Path("/.dockerenv").exists()


def is_docker_runtime() -> bool:
    override = os.getenv("IPOCKET_DOCKER_RUNTIME")
    if override is not None:
        return override.strip().lower() not in _FALSE_VALUES
    return Path("/.dockerenv").exists()
