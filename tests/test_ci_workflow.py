from pathlib import Path


def test_ci_runs_full_pytest_suite():
    ci_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    content = ci_path.read_text(encoding="utf-8")

    assert "quality:" in content
    assert "name: Run Ruff lint" in content
    assert "ruff check ." in content
    assert "name: Run Ruff format check" in content
    assert "ruff format --check ." in content
    assert "name: Run full pytest suite with coverage gate" in content
    assert "pytest tests --cov=app --cov-fail-under=75" in content
    assert "pytest tests/test_health_and_metrics.py" not in content
