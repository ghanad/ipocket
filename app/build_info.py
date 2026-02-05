from __future__ import annotations

import os


def _get_env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if not value:
        return default
    return value


def get_build_info() -> dict[str, str]:
    return {
        "status": "ok",
        "version": _get_env_value("IPOCKET_VERSION", "dev"),
        "commit": _get_env_value("IPOCKET_COMMIT", "unknown"),
        "build_time": _get_env_value("IPOCKET_BUILD_TIME", "unknown"),
    }


def get_display_build_info() -> dict[str, str]:
    info = get_build_info()
    commit = info["commit"]
    if commit != "unknown":
        commit = commit[:7]
    return {
        "version": info["version"],
        "commit": commit,
        "build_time": info["build_time"],
    }
