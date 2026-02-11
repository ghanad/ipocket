from __future__ import annotations

import sqlite3
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from app import auth, db, repository
from app.main import app
from app.models import UserRole


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("IPAM_DB_PATH", str(db_file))
    monkeypatch.delenv("ADMIN_BOOTSTRAP_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
    return db_file


@pytest.fixture
def client(db_path) -> Generator[FastAPITestClient, None, None]:
    auth.clear_tokens()
    with FastAPITestClient(app) as test_client:
        yield test_client
    auth.clear_tokens()


@pytest.fixture
def _setup_connection(db_path) -> Callable[[], sqlite3.Connection]:
    def _factory() -> sqlite3.Connection:
        connection = db.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        db.init_db(connection)
        return connection

    return _factory


@pytest.fixture
def _create_user(db_path, _setup_connection) -> Callable[[str, str, UserRole], None]:
    def _factory(username: str, password: str, role: UserRole) -> None:
        connection = _setup_connection()
        try:
            repository.create_user(
                connection,
                username=username,
                hashed_password=auth.hash_password(password),
                role=role,
            )
        finally:
            connection.close()

    return _factory


@pytest.fixture
def _login(client: FastAPITestClient) -> Callable[[str, str], str]:
    def _factory(username: str, password: str) -> str:
        response = client.post("/login", json={"username": username, "password": password})
        assert response.status_code == 200
        return response.json()["access_token"]

    return _factory


@pytest.fixture
def _auth_headers() -> Callable[[str], dict[str, str]]:
    def _factory(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _factory
