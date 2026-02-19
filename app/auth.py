from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from typing import Optional

from passlib.context import CryptContext

from app import db, repository

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _PWD_CONTEXT.hash(password)


def _is_legacy_sha256_hash(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def verify_and_update_password(
    password: str, hashed_password: str
) -> tuple[bool, Optional[str]]:
    if _is_legacy_sha256_hash(hashed_password):
        legacy_match = secrets.compare_digest(
            hashlib.sha256(password.encode("utf-8")).hexdigest(),
            hashed_password,
        )
        if legacy_match:
            return True, hash_password(password)
        return False, None
    try:
        verified, replacement_hash = _PWD_CONTEXT.verify_and_update(
            password,
            hashed_password,
        )
    except ValueError:
        return False, None
    return bool(verified), replacement_hash


def verify_password(password: str, hashed_password: str) -> bool:
    verified, _ = verify_and_update_password(password, hashed_password)
    return verified


def create_access_token(connection: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    repository.create_session(connection, token=token, user_id=user_id)
    return token


def get_user_id_for_token(connection: sqlite3.Connection, token: str) -> Optional[int]:
    return repository.get_session_user_id(connection, token)


def revoke_access_token(connection: sqlite3.Connection, token: str) -> bool:
    return repository.delete_session(connection, token)


def clear_tokens(connection: sqlite3.Connection | None = None) -> None:
    if connection is not None:
        repository.clear_sessions(connection)
        return

    db_path = os.getenv("IPAM_DB_PATH", "ipocket.db")
    local_connection = db.connect(db_path)
    try:
        repository.clear_sessions(local_connection)
    finally:
        local_connection.close()
