from __future__ import annotations

import ipaddress
import sqlite3
from collections import defaultdict
from typing import Literal, Optional

from sqlalchemy.orm import Session

from app import repository
from app.models import IPAssetType

MissingType = Literal["OS", "BMC", "any"]


def _address_pattern_key(source: str, target: str) -> tuple[str, str, bool] | None:
    try:
        source_address = ipaddress.ip_address(source)
        target_address = ipaddress.ip_address(target)
    except ValueError:
        return None
    if source_address.version != target_address.version:
        return None

    source_network = ipaddress.ip_network(f"{source_address}/16", strict=False)
    target_network = ipaddress.ip_network(f"{target_address}/16", strict=False)
    host_mask = (1 << (source_address.max_prefixlen - 16)) - 1
    same_suffix = int(source_address) & host_mask == int(target_address) & host_mask
    return str(source_network), str(target_network), same_suffix


def get_analytics(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[str, object]:
    """Summarize active Host completion data without mutating inventory."""

    source = repository.get_host_completion_analytics_source(connection_or_session)
    host_ids = {int(host_id) for host_id in source["host_ids"]}
    host_assets: dict[int, dict[str, list[str]]] = {
        host_id: {"OS": [], "BMC": []} for host_id in host_ids
    }
    ip_type_counts = {"BMC": 0, "OS": 0, "VM": 0, "unknown": 0}

    for asset in source["assets"]:
        asset_type = asset.get("type")
        if asset_type in {"BMC", "OS", "VM"}:
            ip_type_counts[asset_type] += 1
        else:
            ip_type_counts["unknown"] += 1

        host_id = asset.get("host_id")
        if asset_type not in {"OS", "BMC"} or host_id not in host_assets:
            continue
        host_assets[host_id][asset_type].append(str(asset.get("ip_address", "")))

    complete_hosts = 0
    os_only = 0
    bmc_only = 0
    unlinked = 0
    confirmed_pairs = 0
    pattern_counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])

    for grouped in host_assets.values():
        os_addresses = grouped["OS"]
        bmc_addresses = grouped["BMC"]
        if os_addresses and bmc_addresses:
            complete_hosts += 1
            confirmed_pairs += len(os_addresses) * len(bmc_addresses)
            for os_address in os_addresses:
                for bmc_address in bmc_addresses:
                    key = _address_pattern_key(os_address, bmc_address)
                    if key is None:
                        continue
                    source_prefix, target_prefix, matches = key
                    pattern_counts[(source_prefix, target_prefix)][
                        0 if matches else 1
                    ] += 1
        elif os_addresses:
            os_only += 1
        elif bmc_addresses:
            bmc_only += 1
        else:
            unlinked += 1

    patterns = [
        {
            "source_prefix": source_prefix,
            "target_prefix": target_prefix,
            "support": counts[0],
            "contradictions": counts[1],
            "coverage_percent": (
                round(counts[0] * 100 / confirmed_pairs, 2) if confirmed_pairs else 0.0
            ),
        }
        for (source_prefix, target_prefix), counts in pattern_counts.items()
        if counts[0] > 0
    ]
    patterns.sort(
        key=lambda pattern: (
            -int(pattern["support"]),
            str(pattern["source_prefix"]),
            str(pattern["target_prefix"]),
        )
    )

    total_hosts = len(host_ids)
    return {
        "total_hosts": total_hosts,
        "complete_hosts": complete_hosts,
        "incomplete_hosts": total_hosts - complete_hosts,
        "breakdown": {
            "os_only": os_only,
            "bmc_only": bmc_only,
            "unlinked": unlinked,
        },
        "confirmed_pairs": confirmed_pairs,
        "patterns": patterns,
        "ip_type_counts": ip_type_counts,
    }


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
