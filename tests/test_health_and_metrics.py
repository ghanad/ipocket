from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "ok"


def test_metrics_returns_required_placeholders() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    for metric in [
        "ipam_ip_total",
        "ipam_ip_archived_total",
        "ipam_ip_unassigned_owner_total",
        "ipam_ip_unassigned_project_total",
        "ipam_ip_unassigned_both_total",
    ]:
        assert metric in body
