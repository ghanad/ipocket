from pathlib import Path


def test_ci_runs_full_pytest_suite():
    ci_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    content = ci_path.read_text(encoding="utf-8")

    assert "name: Run full pytest suite" in content
    assert "pytest tests" in content
    assert "pytest tests/test_health_and_metrics.py" not in content
