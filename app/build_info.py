from __future__ import annotations

import os
from pathlib import Path

from app.environment import is_docker_runtime


def _get_env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    if not value:
        return default
    return value


def _detect_git_commit() -> str | None:
    git_dir = Path(__file__).resolve().parents[1] / ".git"
    if not git_dir.exists():
        return None

    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None

    head_value = head_path.read_text(encoding="utf-8").strip()
    if not head_value:
        return None

    if not head_value.startswith("ref: "):
        return head_value

    ref_name = head_value[5:].strip()
    ref_path = git_dir / ref_name
    if ref_path.exists():
        commit = ref_path.read_text(encoding="utf-8").strip()
        return commit or None

    packed_refs_path = git_dir / "packed-refs"
    if not packed_refs_path.exists():
        return None

    for line in packed_refs_path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        sha, _, ref = line.partition(" ")
        if ref.strip() == ref_name:
            return sha.strip() or None
    return None


def get_build_info() -> dict[str, str]:
    version = _get_env_value("IPOCKET_VERSION", "dev")
    commit = _get_env_value("IPOCKET_COMMIT", "unknown")
    if commit == "unknown":
        detected_commit = _detect_git_commit()
        if detected_commit:
            commit = detected_commit

    docker_tag = os.getenv("IPOCKET_DOCKER_TAG")
    if docker_tag and is_docker_runtime():
        version = docker_tag
    elif version == "dev" and is_docker_runtime() and commit != "unknown":
        version = f"sha-{commit[:7]}"

    return {
        "status": "ok",
        "version": version,
        "commit": commit,
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
