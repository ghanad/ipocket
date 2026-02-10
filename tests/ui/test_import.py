from __future__ import annotations

from pathlib import Path

from app import db, repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes import ui


def test_import_page_includes_sample_csv_links(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(1, "viewer", "x", UserRole.VIEWER, True)
    try:
        response = client.get("/ui/import")
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)

    assert response.status_code == 200
    assert "/static/samples/hosts.csv" in response.text
    assert "/static/samples/ip-assets.csv" in response.text
    assert "Run Nmap" in response.text
    assert "nmap -sn -oX ipocket.xml" in response.text
    assert "nmap -sn -PS80,443 -oX ipocket.xml" in response.text

