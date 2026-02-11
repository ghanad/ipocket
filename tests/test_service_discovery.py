from __future__ import annotations

from fastapi.testclient import TestClient as FastAPITestClient

from app import db, repository
from app.main import app
from app.models import IPAssetType


def test_sd_targets_support_project_grouping(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))

    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project = repository.create_project(connection, name="core")
        repository.create_ip_asset(
            connection, "10.20.0.1", IPAssetType.VM, project_id=project.id
        )
        repository.create_ip_asset(
            connection, "10.20.0.2", IPAssetType.VM, project_id=None
        )
    finally:
        connection.close()

    with FastAPITestClient(app) as client:
        grouped = client.get("/sd/node?group_by=project")
        assert grouped.status_code == 200
        labels = [g["labels"]["project"] for g in grouped.json()]
        assert "core" in labels
        assert "unassigned" in labels
