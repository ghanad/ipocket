from __future__ import annotations

import os

from app import db


def get_db_path() -> str:
    return os.getenv("IPAM_DB_PATH", "ipocket.db")


def get_connection():
    connection = db.connect(get_db_path())
    try:
        yield connection
    finally:
        connection.close()
