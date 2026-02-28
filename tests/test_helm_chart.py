from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHART_ROOT = PROJECT_ROOT / "helm" / "ipocket"


def test_helm_chart_metadata_exists() -> None:
    chart_yaml = (CHART_ROOT / "Chart.yaml").read_text(encoding="utf-8")

    assert "apiVersion: v2" in chart_yaml
    assert "name: ipocket" in chart_yaml
    assert "type: application" in chart_yaml


def test_helm_values_include_runtime_defaults() -> None:
    values_yaml = (CHART_ROOT / "values.yaml").read_text(encoding="utf-8")

    assert "repository: ipocket" in values_yaml
    assert "port: 8000" in values_yaml
    assert "sessionSecret:" in values_yaml
    assert "persistence:" in values_yaml


def test_helm_deployment_template_runs_migrations_and_health_checks() -> None:
    deployment_template = (CHART_ROOT / "templates" / "deployment.yaml").read_text(
        encoding="utf-8"
    )

    assert "alembic upgrade head && uvicorn app.main:app" in deployment_template
    assert "path: /health" in deployment_template
    assert "IPAM_DB_PATH" in deployment_template


def test_helm_templates_include_service_and_secret() -> None:
    service_template = (CHART_ROOT / "templates" / "service.yaml").read_text(
        encoding="utf-8"
    )
    secret_template = (CHART_ROOT / "templates" / "secret.yaml").read_text(
        encoding="utf-8"
    )

    assert "kind: Service" in service_template
    assert "kind: Secret" in secret_template
    assert "SESSION_SECRET" in secret_template
