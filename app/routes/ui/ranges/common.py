from __future__ import annotations

from app.utils import normalize_tag_names

from . import repository


def _parse_selected_tags(
    connection, raw_tags: list[str]
) -> tuple[list[str], list[str]]:
    cleaned_tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
    try:
        selected_tags = normalize_tag_names(cleaned_tags) if cleaned_tags else []
    except ValueError as exc:
        return [], [str(exc)]
    existing_tags = {tag.name for tag in repository.list_tags(connection)}
    missing_tags = [tag for tag in selected_tags if tag not in existing_tags]
    if missing_tags:
        return [], [f"Selected tags do not exist: {', '.join(missing_tags)}."]
    return selected_tags, []


def _build_range_table_rows(
    ranges: list,
    utilization: list[dict[str, object]],
) -> list[dict[str, object]]:
    utilization_by_id = {
        row.get("id"): row for row in utilization if row.get("id") is not None
    }
    rows: list[dict[str, object]] = []
    for ip_range in ranges:
        summary = utilization_by_id.get(ip_range.id, {})
        rows.append(
            {
                "id": ip_range.id,
                "name": ip_range.name,
                "cidr": ip_range.cidr,
                "notes": ip_range.notes,
                "total_usable": summary.get("total_usable"),
                "used": summary.get("used"),
                "free": summary.get("free"),
                "utilization_percent": summary.get("utilization_percent"),
            }
        )
    return rows
