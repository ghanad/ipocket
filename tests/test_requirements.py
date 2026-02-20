from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_requirements_include_pyvmomi_for_vcenter_connector() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "pyvmomi==8.0.3.0.1" in requirements


def test_requirements_include_passlib_for_auth_hashing() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "passlib==1.7.4" in requirements
    assert "bcrypt==4.2.0" in requirements


def test_requirements_include_httpx_dependency() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "httpx==" in requirements


def test_repository_does_not_ship_local_httpx_package() -> None:
    assert not (PROJECT_ROOT / "httpx").exists()
