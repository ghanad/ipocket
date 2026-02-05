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
        project_omid = repository.create_project(connection, name="omid")
        project_payments = repository.create_project(connection, name="payments")
        project_shared = repository.create_project(connection, name="shared")

        owner_ali = repository.create_owner(connection, name="ali")
        owner_reza = repository.create_owner(connection, name="reza")

        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.1",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.VM,
            project_id=project_omid.id,
            owner_id=owner_ali.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.2",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.PHYSICAL,
            project_id=project_omid.id,
            owner_id=owner_reza.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.3",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.VIP,
            project_id=project_payments.id,
            owner_id=owner_reza.id,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.4",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.BMC,
            project_id=project_shared.id,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.5",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.OTHER,
            project_id=None,
            owner_id=None,
        )
        repository.create_ip_asset(
            connection,
            ip_address="10.20.0.6",
            subnet="10.20.0.0/24",
            gateway="10.20.0.254",
            asset_type=IPAssetType.VM,
            project_id=project_omid.id,
            owner_id=owner_ali.id,
        )
        repository.archive_ip_asset(connection, "10.20.0.6")
    finally:
        connection.close()


def _targets(payload: list[dict[str, object]]) -> set[str]:
    targets: set[str] = set()
    for group in payload:
        for target in group["targets"]:
            targets.add(target)
    return targets


def test_sd_node_supports_filters(client) -> None:
    test_client, db_path = client
    _seed_assets(db_path)

    all_response = test_client.get("/sd/node")
    assert all_response.status_code == 200
    all_payload = all_response.json()
    assert len(all_payload) == 1
    assert _targets(all_payload) == {
        "10.20.0.1:9100",
        "10.20.0.2:9100",
        "10.20.0.3:9100",
        "10.20.0.4:9100",
        "10.20.0.5:9100",
    }
    assert "10.20.0.6:9100" not in _targets(all_payload)

    single_project = test_client.get("/sd/node?project=omid")
    assert single_project.status_code == 200
    assert _targets(single_project.json()) == {"10.20.0.1:9100", "10.20.0.2:9100"}

    single_owner = test_client.get("/sd/node?owner=ali")
    assert single_owner.status_code == 200
    assert _targets(single_owner.json()) == {"10.20.0.1:9100"}

    combined = test_client.get("/sd/node?project=omid&owner=reza")
    assert combined.status_code == 200
    assert _targets(combined.json()) == {"10.20.0.2:9100"}

    multiple_projects = test_client.get("/sd/node?project=omid,payments")
    assert multiple_projects.status_code == 200
    assert _targets(multiple_projects.json()) == {
        "10.20.0.1:9100",
        "10.20.0.2:9100",
        "10.20.0.3:9100",
    }

    custom_port = test_client.get("/sd/node?project=omid&port=9200")
    assert custom_port.status_code == 200
    assert _targets(custom_port.json()) == {"10.20.0.1:9200", "10.20.0.2:9200"}

    only_assigned = test_client.get("/sd/node?only_assigned=1")
    assert only_assigned.status_code == 200
    assert _targets(only_assigned.json()) == {
        "10.20.0.1:9100",
        "10.20.0.2:9100",
        "10.20.0.3:9100",
    }

    type_filtered = test_client.get("/sd/node?type=VIP")
    assert type_filtered.status_code == 200
    assert _targets(type_filtered.json()) == {"10.20.0.3:9100"}

    legacy_type_filtered = test_client.get("/sd/node?type=IPMI_ILO")
    assert legacy_type_filtered.status_code == 200
    assert _targets(legacy_type_filtered.json()) == {"10.20.0.4:9100"}


def test_sd_node_group_by_modes(client) -> None:
    test_client, db_path = client
    _seed_assets(db_path)

    group_by_project = test_client.get("/sd/node?group_by=project")
    assert group_by_project.status_code == 200
    by_project = {
        group["labels"]["project"]: set(group["targets"])
        for group in group_by_project.json()
    }
    assert by_project == {
        "omid": {"10.20.0.1:9100", "10.20.0.2:9100"},
        "payments": {"10.20.0.3:9100"},
        "shared": {"10.20.0.4:9100"},
        "unassigned": {"10.20.0.5:9100"},
    }

    group_by_owner = test_client.get("/sd/node?group_by=owner")
    assert group_by_owner.status_code == 200
    by_owner = {
        group["labels"]["owner"]: set(group["targets"])
        for group in group_by_owner.json()
    }
    assert by_owner == {
        "ali": {"10.20.0.1:9100"},
        "reza": {"10.20.0.2:9100", "10.20.0.3:9100"},
        "unassigned": {"10.20.0.4:9100", "10.20.0.5:9100"},
    }

    group_by_project_owner = test_client.get("/sd/node?group_by=project_owner")
    assert group_by_project_owner.status_code == 200
    by_project_owner = {
        (group["labels"]["project"], group["labels"]["owner"]): set(group["targets"])
        for group in group_by_project_owner.json()
    }
    assert by_project_owner == {
        ("omid", "ali"): {"10.20.0.1:9100"},
        ("omid", "reza"): {"10.20.0.2:9100"},
        ("payments", "reza"): {"10.20.0.3:9100"},
        ("shared", "unassigned"): {"10.20.0.4:9100"},
        ("unassigned", "unassigned"): {"10.20.0.5:9100"},
    }


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
    assert _targets(authorized.json()) == {
        "10.20.0.1:9100",
        "10.20.0.2:9100",
        "10.20.0.3:9100",
        "10.20.0.4:9100",
        "10.20.0.5:9100",
    }
