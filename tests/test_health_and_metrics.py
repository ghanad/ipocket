from fastapi.testclient import TestClient

from app import db, repository
from app.main import app
from app.models import IPAssetType


def test_health_check_returns_defaults(monkeypatch) -> None:
    monkeypatch.delenv("IPOCKET_VERSION", raising=False)
    monkeypatch.delenv("IPOCKET_COMMIT", raising=False)
    monkeypatch.delenv("IPOCKET_BUILD_TIME", raising=False)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "dev",
        "commit": "unknown",
        "build_time": "unknown",
    }


def test_health_check_returns_env_override(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_VERSION", "0.1.0")
    monkeypatch.setenv("IPOCKET_COMMIT", "abc123")
    monkeypatch.setenv("IPOCKET_BUILD_TIME", "2024-01-01T00:00:00Z")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "commit": "abc123",
        "build_time": "2024-01-01T00:00:00Z",
    }


def test_metrics_reflect_database_state(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "metrics.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="Core")
        owner = repository.create_owner(connection, name="NetOps")
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.1",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            owner_id=owner.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.2",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.PHYSICAL,
            project_id=project.id,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.3",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.VIP,
            project_id=None,
            owner_id=owner.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.4",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.OTHER,
            project_id=None,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.5",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.BMC,
            project_id=None,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.0.0.6",
            subnet="10.0.0.0/24",
            gateway="10.0.0.254",
            asset_type=IPAssetType.VM,
            project_id=project.id,
            owner_id=owner.id,
        )
        repository.archive_ip_asset(connection, "10.0.0.5")
        repository.archive_ip_asset(connection, "10.0.0.6")
    finally:
        connection.close()

    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    metrics = {}
    for line in response.text.strip().splitlines():
        name, value = line.split()
        metrics[name] = int(value)

    assert metrics["ipam_ip_total"] == 6
    assert metrics["ipam_ip_archived_total"] == 2
    assert metrics["ipam_ip_unassigned_owner_total"] == 2
    assert metrics["ipam_ip_unassigned_project_total"] == 2
    assert metrics["ipam_ip_unassigned_both_total"] == 1
