from __future__ import annotations

import os

from app import auth, db, repository
from app.dependencies import get_db_path
from app.models import UserRole


def bootstrap_admin(connection) -> None:
    username = os.getenv("ADMIN_BOOTSTRAP_USERNAME")
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not username or not password:
        return
    if repository.count_users(connection) > 0:
        return
    repository.create_user(
        connection,
        username=username,
        hashed_password=auth.hash_password(password),
        role=UserRole.ADMIN,
    )


def init_database() -> None:
    connection = db.connect(get_db_path())
    try:
        db.run_migrations(connection=connection)
        bootstrap_admin(connection)
    finally:
        connection.close()
