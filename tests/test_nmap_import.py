from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, repository
from app.imports.nmap import import_nmap_xml, parse_nmap_xml
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes import ui


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with TestClient(app) as test_client:
        yield test_client, db_path
    auth.clear_tokens()


def _load_fixture() -> bytes:
    fixture_path = Path(__file__).parent / "fixtures" / "nmap-scan.xml"
    return fixture_path.read_bytes()


def test_parse_nmap_xml_extracts_up_hosts() -> None:
    payload = _load_fixture()

    result = parse_nmap_xml(payload)

    assert result.errors == []
    assert result.ip_addresses == ["10.0.0.10", "10.0.0.12"]


def test_nmap_dry_run_does_not_create(client) -> None:
    _, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        payload = _load_fixture()
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = import_nmap_xml(connection, payload, dry_run=True, now=now)

        assert result.discovered_up_hosts == 2
        assert result.new_ips_created == 2
        assert result.existing_ips_seen == 0
        assert list(repository.list_active_ip_assets(connection)) == []
    finally:
        connection.close()


def test_nmap_apply_creates_new_other_assets(client) -> None:
    _, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        payload = _load_fixture()
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result = import_nmap_xml(connection, payload, dry_run=False, now=now)

        assert result.new_ips_created == 2
        assets = list(repository.list_active_ip_assets(connection))
        assert len(assets) == 2
        expected_note = f"Discovered via nmap upload at {now.isoformat(timespec='seconds')}"
        for asset in assets:
            assert asset.asset_type == IPAssetType.OTHER
            assert asset.notes == expected_note
    finally:
        connection.close()


def test_nmap_existing_assets_are_not_overwritten(client) -> None:
    _, db_path = client
    connection = db.connect(str(db_path))
    try:
        db.init_db(connection)
        existing = repository.create_ip_asset(
            connection,
            ip_address="10.0.0.10",
            asset_type=IPAssetType.VM,
            notes="Existing notes",
        )
        payload = _load_fixture()

        result = import_nmap_xml(connection, payload, dry_run=False)

        assert result.new_ips_created == 1
        assert result.existing_ips_seen == 1
        asset = repository.get_ip_asset_by_ip(connection, existing.ip_address)
        assert asset is not None
        assert asset.asset_type == IPAssetType.VM
        assert asset.notes == "Existing notes"
        new_asset = repository.get_ip_asset_by_ip(connection, "10.0.0.12")
        assert new_asset is not None
        assert new_asset.asset_type == IPAssetType.OTHER
    finally:
        connection.close()


def test_nmap_viewer_cannot_apply(client) -> None:
    test_client, _ = client
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "viewer", "x", UserRole.VIEWER, True)
    try:
        payload = _load_fixture()
        response = test_client.post(
            "/ui/import-nmap",
            files={"nmap_file": ("scan.xml", payload, "text/xml")},
        )
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 403
