from __future__ import annotations

from typing import Optional

from app import repository
from app.models import IPAssetType
from app.utils import normalize_tag_names

_PROMETHEUS_DETAIL_LIMIT = 100


def _safe_normalize_tags(tag_values: object) -> list[str]:
    if not isinstance(tag_values, list):
        return []
    prepared = [str(value).strip() for value in tag_values if str(value).strip()]
    if not prepared:
        return []
    try:
        return normalize_tag_names(prepared)
    except ValueError:
        return prepared


def _label_or_unassigned(value: Optional[str]) -> str:
    if value is None:
        return "Unassigned"
    stripped = value.strip()
    return stripped if stripped else "Unassigned"


def _format_tag_list(tag_names: list[str]) -> str:
    return ", ".join(tag_names) if tag_names else "none"


def _build_prometheus_dry_run_change_logs(
    connection,
    *,
    ip_assets: list[dict[str, object]],
) -> list[str]:
    if connection is None:
        return []

    project_names = {
        project.id: project.name for project in repository.list_projects(connection)
    }
    host_names = {host.id: host.name for host in repository.list_hosts(connection)}
    detail_lines: list[str] = []

    for asset in ip_assets:
        ip_address = str(asset.get("ip_address") or "").strip()
        if not ip_address:
            continue
        desired_type = str(asset.get("type") or IPAssetType.OTHER.value)
        desired_project = (
            _label_or_unassigned(str(asset["project_name"]))
            if asset.get("project_name") is not None
            else None
        )
        desired_host = (
            _label_or_unassigned(str(asset["host_name"]))
            if asset.get("host_name") is not None
            else None
        )
        desired_archived = bool(asset.get("archived", False))
        desired_tags = _safe_normalize_tags(asset.get("tags"))
        desired_notes = str(asset.get("notes") or "") or None
        preserve_notes = bool(asset.get("preserve_existing_notes"))
        preserve_type = bool(asset.get("preserve_existing_type"))
        notes_provided = "notes" in asset or asset.get("notes") is not None

        existing = repository.get_ip_asset_by_ip(connection, ip_address)
        if existing is None:
            detail_lines.append(
                f"- [CREATE] {ip_address}: type={desired_type}; "
                f"project={_label_or_unassigned(desired_project)}; "
                f"host={_label_or_unassigned(desired_host)}; "
                f"tags=[{_format_tag_list(desired_tags)}]; "
                f"notes={'set' if desired_notes else 'empty'}; "
                f"archived={str(desired_archived).lower()}."
            )
            continue

        existing_project = _label_or_unassigned(project_names.get(existing.project_id))
        existing_host = _label_or_unassigned(host_names.get(existing.host_id))
        existing_tags = repository.list_tags_for_ip_assets(
            connection, [existing.id]
        ).get(existing.id, [])

        if asset.get("tags") is None:
            target_tags = existing_tags
        elif bool(asset.get("merge_tags")):
            target_tags = _safe_normalize_tags([*existing_tags, *desired_tags])
        else:
            target_tags = desired_tags

        should_update_notes = notes_provided
        note_preserved = False
        if should_update_notes and preserve_notes and existing.notes:
            should_update_notes = False
            note_preserved = True
        target_notes = desired_notes if should_update_notes else existing.notes
        target_project = _label_or_unassigned(desired_project or existing_project)
        target_host = _label_or_unassigned(desired_host or existing_host)
        target_type = existing.asset_type.value if preserve_type else desired_type

        changes: list[str] = []
        if existing.asset_type.value != target_type:
            changes.append(f"type {existing.asset_type.value} -> {target_type}")
        if existing_project != target_project:
            changes.append(f"project {existing_project} -> {target_project}")
        if existing_host != target_host:
            changes.append(f"host {existing_host} -> {target_host}")
        if existing_tags != target_tags:
            added = [tag for tag in target_tags if tag not in existing_tags]
            removed = [tag for tag in existing_tags if tag not in target_tags]
            tag_changes: list[str] = []
            if added:
                tag_changes.append(f"+[{_format_tag_list(added)}]")
            if removed:
                tag_changes.append(f"-[{_format_tag_list(removed)}]")
            changes.append(f"tags {' '.join(tag_changes)}")
        if (existing.notes or None) != (target_notes or None):
            changes.append(
                "notes "
                f"{'set' if existing.notes else 'empty'} -> "
                f"{'set' if target_notes else 'empty'}"
            )
        elif note_preserved and changes:
            changes.append("notes preserved (existing note kept)")
        if bool(existing.archived) != desired_archived:
            changes.append(
                f"archived {str(bool(existing.archived)).lower()} -> {str(desired_archived).lower()}"
            )

        if changes:
            detail_lines.append(f"- [UPDATE] {ip_address}: {'; '.join(changes)}.")
        else:
            detail_lines.append(f"- [SKIP] {ip_address}: no field changes.")

    if not detail_lines:
        return ["Dry-run per-IP change details: no valid IP assets extracted."]

    if len(detail_lines) > _PROMETHEUS_DETAIL_LIMIT:
        remaining = len(detail_lines) - _PROMETHEUS_DETAIL_LIMIT
        trimmed = detail_lines[:_PROMETHEUS_DETAIL_LIMIT]
        trimmed.append(f"- Dry-run detail truncated: {remaining} more IP(s).")
        detail_lines = trimmed

    return ["Dry-run per-IP change details:", *detail_lines]
