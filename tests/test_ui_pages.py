from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_path))
    auth.clear_tokens()
    with TestClient(app) as test_client:
        yield test_client
    auth.clear_tokens()


def test_needs_assignment_page_renders(client) -> None:
    response = client.get("/ui/ip-assets/needs-assignment?filter=project")
    assert response.status_code == 200
