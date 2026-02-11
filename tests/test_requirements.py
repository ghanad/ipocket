from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_requirements_include_pyvmomi_for_vcenter_connector() -> None:
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "pyvmomi==8.0.3.0.1" in requirements
