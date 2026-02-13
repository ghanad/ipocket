from __future__ import annotations

from typing import Optional

from app import repository
from app.models import IPAssetType
from app.utils import normalize_tag_names

_HIGH_RISK_DELETE_TAGS = {"prod", "production", "critical", "flagged"}


def _friendly_audit_changes(changes: str) -> dict[str, str]:
    normalized = (changes or "").strip()
    if not normalized:
        return {"summary": "No additional details.", "raw": ""}

    if normalized.startswith("Created IP asset "):
        raw_payload = normalized.removeprefix("Created IP asset ").strip()
        compact_payload = raw_payload.strip("()")
        raw_map: dict[str, str] = {}
        for chunk in compact_payload.split(","):
            key, _, value = chunk.strip().partition("=")
            if key:
                raw_map[key.strip()] = value.strip()
        summary_parts = [
            f"Type: {raw_map.get('type', 'Unknown')}",
            (
                "Project: Unassigned"
                if raw_map.get("project_id") in {None, "", "None"}
                else f"Project ID: {raw_map.get('project_id')}"
            ),
            (
                "Host: Unassigned"
                if raw_map.get("host_id") in {None, "", "None"}
                else f"Host ID: {raw_map.get('host_id')}"
            ),
            f"Notes: {(raw_map.get('notes') or 'No notes').strip() or 'No notes'}",
        ]
        return {"summary": "; ".join(summary_parts), "raw": normalized}

    return {"summary": normalized, "raw": normalized}


def _delete_requires_exact_ip(asset, tag_names: list[str]) -> bool:
    normalized_tags = {tag.lower() for tag in tag_names}
    return bool(
        asset.project_id
        or asset.host_id
        or asset.asset_type == IPAssetType.VIP
        or normalized_tags.intersection(_HIGH_RISK_DELETE_TAGS)
    )


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


def _ip_asset_form_context(
    *,
    title: str,
    asset_id: Optional[int],
    ip_address: str,
    asset_type: str,
    project_id: Optional[int],
    host_id: Optional[int],
    notes: Optional[str],
    tags: list[str],
    projects,
    hosts,
    tags_catalog,
    errors: list[str],
    mode: str,
    action_url: str,
    submit_label: str,
) -> dict:
    return {
        "title": title,
        "asset": {
            "id": asset_id,
            "ip_address": ip_address,
            "type": asset_type,
            "project_id": project_id or "",
            "host_id": host_id or "",
            "notes": notes or "",
            "tags": tags,
        },
        "projects": projects,
        "hosts": hosts,
        "tags": tags_catalog,
        "types": [asset.value for asset in IPAssetType],
        "errors": errors,
        "mode": mode,
        "action_url": action_url,
        "submit_label": submit_label,
    }
