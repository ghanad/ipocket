from __future__ import annotations

from app import db


def test_connect_applies_sqlite_concurrency_pragmas(tmp_path) -> None:
    db_path = tmp_path / "test.db"

    connection = db.connect(str(db_path))
    try:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 1
        assert int(busy_timeout) == 5000
    finally:
        connection.close()


def test_connect_applies_pragmas_for_each_new_connection(tmp_path) -> None:
    db_path = tmp_path / "test.db"

    first_connection = db.connect(str(db_path))
    try:
        first_connection.execute("PRAGMA busy_timeout=0;")
        first_connection.execute("PRAGMA synchronous=OFF;")
    finally:
        first_connection.close()

    second_connection = db.connect(str(db_path))
    try:
        synchronous = second_connection.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = second_connection.execute("PRAGMA busy_timeout").fetchone()[0]

        assert int(synchronous) == 1
        assert int(busy_timeout) == 5000
    finally:
        second_connection.close()
