from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse

from app import repository
from app.connectors.prometheus import (
    PrometheusConnectorError,
    build_import_bundle_from_prometheus,
    extract_ip_assets_from_result,
    fetch_prometheus_query_result,
    import_bundle_via_pipeline as import_prometheus_bundle_via_pipeline,
)
from app.connectors.vcenter import (
    VCenterConnectorError,
    build_import_bundle,
    fetch_vcenter_inventory,
    import_bundle_via_pipeline as import_vcenter_bundle_via_pipeline,
)
from app.dependencies import get_connection
from app.models import IPAssetType, UserRole
from app.utils import normalize_tag_names, split_tag_string
from .utils import _render_template
from .utils import _parse_form_data, get_current_ui_user

router = APIRouter()
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


def _default_vcenter_form_state() -> dict[str, object]:
    return {
        "server": "",
        "username": "",
        "password": "",
        "port": "443",
        "insecure": False,
        "mode": "dry-run",
    }


def _default_prometheus_form_state() -> dict[str, object]:
    return {
        "prometheus_url": "",
        "query": "",
        "ip_label": "instance",
        "asset_type": IPAssetType.OTHER.value,
        "project_name": "",
        "tags": "",
        "token": "",
        "insecure": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _connectors_context(
    *,
    active_tab: str = "overview",
    vcenter_form_state: Optional[dict[str, object]] = None,
    vcenter_errors: Optional[list[str]] = None,
    vcenter_logs: Optional[list[str]] = None,
    prometheus_form_state: Optional[dict[str, object]] = None,
    prometheus_errors: Optional[list[str]] = None,
    prometheus_logs: Optional[list[str]] = None,
    toast_messages: Optional[list[dict[str, str]]] = None,
) -> dict[str, object]:
    return {
        "title": "ipocket - Connectors",
        "active_tab": active_tab,
        "vcenter_form_state": vcenter_form_state or _default_vcenter_form_state(),
        "vcenter_errors": vcenter_errors or [],
        "vcenter_logs": vcenter_logs or [],
        "prometheus_form_state": prometheus_form_state
        or _default_prometheus_form_state(),
        "prometheus_errors": prometheus_errors or [],
        "prometheus_logs": prometheus_logs or [],
        "toast_messages": toast_messages or [],
    }


@router.get("/ui/connectors", response_class=HTMLResponse)
def ui_connectors(
    request: Request,
    tab: Optional[str] = Query(default=None),
) -> HTMLResponse:
    active_tab = tab if tab in {"overview", "vcenter", "prometheus"} else "overview"
    return _render_template(
        request,
        "connectors.html",
        _connectors_context(active_tab=active_tab),
        active_nav="connectors",
    )


def _run_vcenter_connector(
    *,
    connection,
    user,
    server: str,
    username: str,
    password: str,
    port: int,
    insecure: bool,
    dry_run: bool,
) -> tuple[list[str], list[str], int, int]:
    logs: list[str] = []

    hosts, vms, inventory_warnings = fetch_vcenter_inventory(
        server=server,
        username=username,
        password=password,
        port=port,
        insecure=insecure,
    )
    logs.append(f"Connected to vCenter '{server}'.")
    logs.append(f"Collected {len(hosts)} hosts and {len(vms)} VMs.")

    bundle, bundle_warnings = build_import_bundle(hosts, vms)
    data = bundle.get("data", {})
    ip_assets = data.get("ip_assets", []) if isinstance(data, dict) else []
    total_assets = len(ip_assets) if isinstance(ip_assets, list) else 0
    logs.append(f"Prepared bundle with {total_assets} IP assets.")

    result = import_vcenter_bundle_via_pipeline(
        connection,
        bundle=bundle,
        user=user,
        dry_run=dry_run,
    )

    mode_label = "dry-run" if dry_run else "apply"
    total = result.summary.total()
    logs.append(
        f"Import mode: {mode_label}. Summary create={total.would_create}, update={total.would_update}, skip={total.would_skip}."
    )
    import_warning_count = len(result.warnings)
    import_error_count = len(result.errors)
    if result.warnings:
        logs.append(f"Import warnings: {len(result.warnings)}")
        for issue in result.warnings:
            logs.append(f"- {issue.location}: {issue.message}")
    if result.errors:
        logs.append(f"Import errors: {len(result.errors)}")
        for issue in result.errors:
            logs.append(f"- {issue.location}: {issue.message}")
    elif not result.warnings:
        logs.append("Import completed without warnings or errors.")

    combined_warnings = [*inventory_warnings, *bundle_warnings]
    return logs, combined_warnings, import_warning_count, import_error_count


def _run_prometheus_connector(
    *,
    connection,
    user,
    prometheus_url: str,
    query: str,
    ip_label: str,
    asset_type: str,
    project_name: Optional[str],
    tags: Optional[list[str]],
    token: Optional[str],
    insecure: bool,
    timeout: int,
    dry_run: bool,
) -> tuple[list[str], list[str], int, int]:
    logs: list[str] = []

    records = fetch_prometheus_query_result(
        prometheus_url=prometheus_url,
        query=query,
        token=token,
        timeout=timeout,
        insecure=insecure,
    )
    logs.append(f"Connected to Prometheus '{prometheus_url}'.")
    logs.append(f"Collected {len(records)} metric samples.")

    ip_assets, extraction_warnings = extract_ip_assets_from_result(
        records,
        ip_label=ip_label,
        default_type=asset_type,
        project_name=project_name,
        tags=tags,
        query=query,
    )
    logs.append(f"Prepared {len(ip_assets)} IP assets from query results.")
    if dry_run:
        preview_limit = 20
        preview_ips = [
            str(asset.get("ip_address")) for asset in ip_assets[:preview_limit]
        ]
        if preview_ips:
            logs.append(
                f"Dry-run IP preview ({len(ip_assets)}): {', '.join(preview_ips)}"
            )
            if len(ip_assets) > preview_limit:
                logs.append(
                    f"Dry-run IP preview truncated: {len(ip_assets) - preview_limit} more IP(s)."
                )
        else:
            logs.append("Dry-run IP preview: no valid IPs were extracted.")
        logs.extend(
            _build_prometheus_dry_run_change_logs(connection, ip_assets=ip_assets)
        )

    bundle, bundle_warnings = build_import_bundle_from_prometheus(ip_assets)
    result = import_prometheus_bundle_via_pipeline(
        connection,
        bundle=bundle,
        user=user,
        dry_run=dry_run,
    )

    mode_label = "dry-run" if dry_run else "apply"
    total = result.summary.total()
    logs.append(
        f"Import mode: {mode_label}. Summary create={total.would_create}, update={total.would_update}, skip={total.would_skip}."
    )
    logs.append(
        "IP assets summary: "
        f"create={result.summary.ip_assets.would_create}, "
        f"update={result.summary.ip_assets.would_update}, "
        f"skip={result.summary.ip_assets.would_skip}."
    )
    import_warning_count = len(result.warnings)
    import_error_count = len(result.errors)
    if result.warnings:
        logs.append(f"Import warnings: {len(result.warnings)}")
        for issue in result.warnings:
            logs.append(f"- {issue.location}: {issue.message}")
    if result.errors:
        logs.append(f"Import errors: {len(result.errors)}")
        for issue in result.errors:
            logs.append(f"- {issue.location}: {issue.message}")
    elif not result.warnings:
        logs.append("Import completed without warnings or errors.")

    combined_warnings = [*extraction_warnings, *bundle_warnings]
    return logs, combined_warnings, import_warning_count, import_error_count


@router.post("/ui/connectors/vcenter/run", response_class=HTMLResponse)
async def ui_run_vcenter_connector(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    server = (form_data.get("server") or "").strip()
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""
    mode = (form_data.get("mode") or "dry-run").strip().lower()
    port_raw = (form_data.get("port") or "443").strip()
    insecure = form_data.get("insecure") == "1"

    errors: list[str] = []
    if not server:
        errors.append("vCenter server is required.")
    if not username:
        errors.append("vCenter username is required.")
    if not password:
        errors.append("vCenter password is required.")
    if mode not in {"dry-run", "apply"}:
        errors.append("Mode must be dry-run or apply.")
    try:
        port = int(port_raw)
        if port <= 0 or port > 65535:
            raise ValueError
    except ValueError:
        errors.append("Port must be a valid number between 1 and 65535.")
        port = 443

    form_state = {
        "server": server,
        "username": username,
        "password": "",
        "port": str(port),
        "insecure": insecure,
        "mode": mode if mode in {"dry-run", "apply"} else "dry-run",
    }
    if errors:
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="vcenter",
                vcenter_form_state=form_state,
                vcenter_errors=errors,
            ),
            active_nav="connectors",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if mode == "apply" and user.role != UserRole.EDITOR:
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="vcenter",
                vcenter_form_state=form_state,
                toast_messages=[
                    {
                        "type": "error",
                        "message": "Apply mode is restricted to editor accounts.",
                    }
                ],
            ),
            active_nav="connectors",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    logs: list[str] = []
    toast_messages: list[dict[str, str]] = []
    try:
        (
            run_logs,
            warnings,
            import_warning_count,
            import_error_count,
        ) = _run_vcenter_connector(
            connection=connection,
            user=user,
            server=server,
            username=username,
            password=password,
            port=port,
            insecure=insecure,
            dry_run=mode == "dry-run",
        )
        logs.extend(run_logs)
        if warnings:
            logs.append(f"Connector warnings: {len(warnings)}")
            for warning in warnings:
                logs.append(f"- {warning}")
        if import_error_count > 0:
            toast_messages.append(
                {
                    "type": "error",
                    "message": f"vCenter {mode} completed with {import_error_count} import error(s).",
                }
            )
        elif import_warning_count > 0 or warnings:
            toast_messages.append(
                {
                    "type": "warning",
                    "message": f"vCenter {mode} completed with warnings. Review execution log.",
                }
            )
        else:
            toast_messages.append(
                {
                    "type": "success",
                    "message": f"vCenter {mode} completed successfully.",
                }
            )
    except VCenterConnectorError as exc:
        logs.append(f"Connector failed: {exc}")
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="vcenter",
                vcenter_form_state=form_state,
                vcenter_logs=logs,
                toast_messages=[
                    {
                        "type": "error",
                        "message": "vCenter connector execution failed.",
                    }
                ],
            ),
            active_nav="connectors",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _render_template(
        request,
        "connectors.html",
        _connectors_context(
            active_tab="vcenter",
            vcenter_form_state=form_state,
            vcenter_logs=logs,
            toast_messages=toast_messages,
        ),
        active_nav="connectors",
    )


@router.post("/ui/connectors/prometheus/run", response_class=HTMLResponse)
async def ui_run_prometheus_connector(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    prometheus_url = (form_data.get("prometheus_url") or "").strip()
    query = (form_data.get("query") or "").strip()
    ip_label = (form_data.get("ip_label") or "").strip()
    asset_type_raw = (form_data.get("asset_type") or IPAssetType.OTHER.value).strip()
    project_name_raw = (form_data.get("project_name") or "").strip()
    tags_raw = (form_data.get("tags") or "").strip()
    token = (form_data.get("token") or "").strip() or None
    mode = (form_data.get("mode") or "dry-run").strip().lower()
    insecure = form_data.get("insecure") == "1"
    timeout_raw = (form_data.get("timeout") or "30").strip()

    errors: list[str] = []
    if not prometheus_url:
        errors.append("Prometheus URL is required.")
    if not query:
        errors.append("PromQL query is required.")
    if not ip_label:
        errors.append("IP label is required.")
    if mode not in {"dry-run", "apply"}:
        errors.append("Mode must be dry-run or apply.")

    try:
        timeout = int(timeout_raw)
        if timeout <= 0:
            raise ValueError
    except ValueError:
        errors.append("Timeout must be a positive integer.")
        timeout = 30

    try:
        asset_type = IPAssetType.normalize(asset_type_raw).value
    except ValueError:
        errors.append("Asset type must be one of OS, BMC, VM, VIP, OTHER.")
        asset_type = IPAssetType.OTHER.value

    project_name = project_name_raw or None
    tags = split_tag_string(tags_raw) if tags_raw else None

    form_state = {
        "prometheus_url": prometheus_url,
        "query": query,
        "ip_label": ip_label,
        "asset_type": asset_type,
        "project_name": project_name_raw,
        "tags": tags_raw,
        "token": "",
        "insecure": insecure,
        "mode": mode if mode in {"dry-run", "apply"} else "dry-run",
        "timeout": str(timeout),
    }
    if errors:
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="prometheus",
                prometheus_form_state=form_state,
                prometheus_errors=errors,
            ),
            active_nav="connectors",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if mode == "apply" and user.role != UserRole.EDITOR:
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="prometheus",
                prometheus_form_state=form_state,
                toast_messages=[
                    {
                        "type": "error",
                        "message": "Apply mode is restricted to editor accounts.",
                    }
                ],
            ),
            active_nav="connectors",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    logs: list[str] = []
    toast_messages: list[dict[str, str]] = []
    try:
        (
            run_logs,
            warnings,
            import_warning_count,
            import_error_count,
        ) = _run_prometheus_connector(
            connection=connection,
            user=user,
            prometheus_url=prometheus_url,
            query=query,
            ip_label=ip_label,
            asset_type=asset_type,
            project_name=project_name,
            tags=tags,
            token=token,
            insecure=insecure,
            timeout=timeout,
            dry_run=mode == "dry-run",
        )
        logs.extend(run_logs)
        if warnings:
            logs.append(f"Connector warnings: {len(warnings)}")
            for warning in warnings:
                logs.append(f"- {warning}")
        if import_error_count > 0:
            toast_messages.append(
                {
                    "type": "error",
                    "message": f"Prometheus {mode} completed with {import_error_count} import error(s).",
                }
            )
        elif import_warning_count > 0 or warnings:
            toast_messages.append(
                {
                    "type": "warning",
                    "message": "Prometheus "
                    f"{mode} completed with warnings. Review execution log.",
                }
            )
        else:
            toast_messages.append(
                {
                    "type": "success",
                    "message": f"Prometheus {mode} completed successfully.",
                }
            )
    except PrometheusConnectorError as exc:
        logs.append(f"Connector failed: {exc}")
        return _render_template(
            request,
            "connectors.html",
            _connectors_context(
                active_tab="prometheus",
                prometheus_form_state=form_state,
                prometheus_logs=logs,
                toast_messages=[
                    {
                        "type": "error",
                        "message": "Prometheus connector execution failed.",
                    }
                ],
            ),
            active_nav="connectors",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return _render_template(
        request,
        "connectors.html",
        _connectors_context(
            active_tab="prometheus",
            prometheus_form_state=form_state,
            prometheus_logs=logs,
            toast_messages=toast_messages,
        ),
        active_nav="connectors",
    )
