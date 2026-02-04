from fastapi.testclient import TestClient

from app import db, repository
from app.main import app
from app.models import IPAssetType


def test_health_check_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "ok"


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
            asset_type=IPAssetType.IPMI_ILO,
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
