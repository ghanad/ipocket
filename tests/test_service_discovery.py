from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db, repository
from app.main import app
from app.models import IPAssetType


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    monkeypatch.delenv("IPOCKET_SD_TOKEN", raising=False)
    with TestClient(app) as test_client:
        yield test_client, db_path


def _seed_assets(db_path) -> None:
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        project_core = repository.create_project(connection, name="Core")
        repository.create_project(connection, name="Payments")
        owner_netops = repository.create_owner(connection, name="NetOps")

        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.1",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.VM,
            project_id=project_core.id,
            owner_id=owner_netops.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.2",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.PHYSICAL,
            project_id=project_core.id,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.3",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.OTHER,
            project_id=None,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.4",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.VIP,
            project_id=project_core.id,
            owner_id=owner_netops.id,
        )
        repository.archive_ip_asset(connection, "10.20.0.4")
    finally:
        connection.close()


def test_sd_node_prometheus_structure_and_filters(client) -> None:
    test_client, db_path = client
    _seed_assets(db_path)

    response = test_client.get("/sd/node")
    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload, list)
    assert len(payload) == 3
    assert all("targets" in group for group in payload)
    assert all("labels" in group for group in payload)

    target_map = {group["targets"][0]: group["labels"] for group in payload}
    assert "10.20.0.4:9100" not in target_map

    assert target_map["10.20.0.1:9100"] == {
        "project": "Core",
        "owner": "NetOps",
        "type": "VM",
    }
    assert target_map["10.20.0.2:9100"] == {
        "project": "Core",
        "owner": "unassigned",
        "type": "PHYSICAL",
    }
    assert target_map["10.20.0.3:9100"] == {
        "project": "unassigned",
        "owner": "unassigned",
        "type": "OTHER",
    }

    custom_port_response = test_client.get("/sd/node?port=9200")
    assert custom_port_response.status_code == 200
    custom_targets = {
        group["targets"][0] for group in custom_port_response.json()
    }
    assert "10.20.0.1:9200" in custom_targets

    assigned_response = test_client.get("/sd/node?only_assigned=1")
    assert assigned_response.status_code == 200
    assigned_targets = [
        group["targets"][0] for group in assigned_response.json()
    ]
    assert assigned_targets == ["10.20.0.1:9100"]

    filtered_response = test_client.get("/sd/node?project=Core")
    assert filtered_response.status_code == 200
    filtered_targets = [
        group["targets"][0] for group in filtered_response.json()
    ]
    assert filtered_targets == ["10.20.0.1:9100", "10.20.0.2:9100"]


def test_sd_node_optional_token_auth(client, monkeypatch) -> None:
    test_client, db_path = client
    _seed_assets(db_path)
    monkeypatch.setenv("IPOCKET_SD_TOKEN", "sd-secret")

    unauthorized = test_client.get("/sd/node")
    assert unauthorized.status_code == 401

    wrong_token = test_client.get("/sd/node", headers={"X-SD-Token": "wrong"})
    assert wrong_token.status_code == 401

    authorized = test_client.get("/sd/node", headers={"X-SD-Token": "sd-secret"})
    assert authorized.status_code == 200
    assert len(authorized.json()) == 3
