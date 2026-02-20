from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterator

from app import db
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def get_db_path() -> str:
    return os.getenv("IPAM_DB_PATH", "ipocket.db")


@lru_cache(maxsize=8)
def _get_session_factory(db_path: str) -> sessionmaker[Session]:
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_db_session(db_path: str | None = None) -> Session:
    target_db_path = db_path or get_db_path()
    session = _get_session_factory(target_db_path)()
    session.execute(text("PRAGMA foreign_keys = ON"))
    return session


def get_session() -> Iterator[Session]:
    session = create_db_session()
    try:
        yield session
    finally:
        session.close()


def get_connection():
    connection = db.connect(get_db_path())
    try:
        yield connection
    finally:
        connection.close()
