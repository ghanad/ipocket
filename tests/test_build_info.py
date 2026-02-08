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
