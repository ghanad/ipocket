from __future__ import annotations

from app import build_info


def test_build_info_uses_docker_tag_when_docker(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_DOCKER_RUNTIME", "1")
    monkeypatch.setenv("IPOCKET_DOCKER_TAG", "v1.2.3")
    monkeypatch.setenv("IPOCKET_VERSION", "0.1.0")

    info = build_info.get_build_info()

    assert info["version"] == "v1.2.3"


def test_build_info_ignores_docker_tag_when_not_docker(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_DOCKER_RUNTIME", "0")
    monkeypatch.setenv("IPOCKET_DOCKER_TAG", "v2.0.0")
    monkeypatch.setenv("IPOCKET_VERSION", "0.9.0")

    info = build_info.get_build_info()

    assert info["version"] == "0.9.0"


def test_build_info_detects_git_commit_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("IPOCKET_COMMIT", raising=False)
    monkeypatch.setattr(build_info, "_detect_git_commit", lambda: "abcdef123456")

    info = build_info.get_build_info()

    assert info["commit"] == "abcdef123456"


def test_build_info_uses_commit_based_version_in_docker_when_version_unset(
    monkeypatch,
) -> None:
    monkeypatch.setenv("IPOCKET_DOCKER_RUNTIME", "1")
    monkeypatch.delenv("IPOCKET_VERSION", raising=False)
    monkeypatch.delenv("IPOCKET_DOCKER_TAG", raising=False)
    monkeypatch.delenv("IPOCKET_COMMIT", raising=False)
    monkeypatch.setattr(build_info, "_detect_git_commit", lambda: "1234567890abcdef")

    info = build_info.get_build_info()

    assert info["version"] == "sha-1234567"
