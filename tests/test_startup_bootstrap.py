from __future__ import annotations

from app import repository
from app.models import UserRole
from app.startup import bootstrap_admin


def test_bootstrap_admin_creates_superuser(monkeypatch, _setup_connection) -> None:
    monkeypatch.setenv("ADMIN_BOOTSTRAP_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "admin-pass")

    connection = _setup_connection()
    try:
        bootstrap_admin(connection)
        user = repository.get_user_by_username(connection, "admin")
        assert user is not None
        assert user.role == UserRole.SUPERUSER
    finally:
        connection.close()
