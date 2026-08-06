from __future__ import annotations

import sqlite3
from typing import Literal, Optional

from sqlalchemy.orm import Session

from app import repository
from app.models import IPAssetType

MissingType = Literal["OS", "BMC", "any"]


def _page(records: list[dict[str, object]], limit: int) -> dict[str, object]:
    has_more = len(records) > limit
    items = records[:limit]
    next_cursor = int(items[-1]["host_id"]) if has_more and items else None
    return {"items": items, "next_cursor": next_cursor}


def list_incomplete_hosts(
    connection_or_session: sqlite3.Connection | Session,
    *,
    missing: MissingType = "any",
    limit: int = 100,
    cursor: Optional[int] = None,
) -> dict[str, object]:
    missing_type = None if missing == "any" else IPAssetType(missing)
    records = repository.list_host_completion_records(
        connection_or_session,
        kind="incomplete",
        missing_type=missing_type,
        after_host_id=cursor,
        limit=limit + 1,
    )
    for record in records:
        record["missing"] = "BMC" if record["os_assets"] else "OS"
    return _page(records, limit)


def list_confirmed_examples(
    connection_or_session: sqlite3.Connection | Session,
    *,
    limit: int = 100,
    cursor: Optional[int] = None,
) -> dict[str, object]:
    records = repository.list_host_completion_records(
        connection_or_session,
        kind="complete",
        after_host_id=cursor,
        limit=limit + 1,
    )
    return _page(records, limit)
