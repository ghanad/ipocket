from __future__ import annotations

import os

from app.environment import is_docker_runtime


def _get_env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if not value:
        return default
    return value


def get_build_info() -> dict[str, str]:
    version = _get_env_value("IPOCKET_VERSION", "dev")
    docker_tag = os.getenv("IPOCKET_DOCKER_TAG")
    if docker_tag and is_docker_runtime():
        version = docker_tag
    return {
        "status": "ok",
        "version": version,
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
