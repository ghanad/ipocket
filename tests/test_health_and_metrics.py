from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _parse_metrics(text: str) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        name, value = line.split(" ", 1)
        metrics[name] = int(float(value))
    return metrics


def test_health_and_metrics_endpoints() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        metrics_response = client.get("/metrics")
        assert metrics_response.status_code == 200
        metrics = _parse_metrics(metrics_response.text)
        assert "ipam_ip_total" in metrics
        assert "ipam_ip_archived_total" in metrics
        assert "ipam_ip_unassigned_project_total" in metrics
        assert "ipam_ip_unassigned_owner_total" in metrics
        assert "ipam_ip_unassigned_both_total" in metrics
        assert metrics["ipam_ip_total"] == 0
        assert metrics["ipam_ip_archived_total"] == 0
        assert metrics["ipam_ip_unassigned_project_total"] == 0
        assert metrics["ipam_ip_unassigned_owner_total"] == 0
        assert metrics["ipam_ip_unassigned_both_total"] == 0
