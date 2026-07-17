from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db, repository
from app.dependencies import get_db_path
from app.models import IPAssetType, UserRole
from app.routes.ui.utils import _parse_form_data, _render_template, get_current_ui_user
from app.utils import split_tag_string
from .common import _finalize_job_logs, _redact_connector_logs
from .forms import _connectors_context
from .job_store import _create_connector_job, _update_connector_job

from app.connectors.cassandra import (
    CassandraConnectorError,
    build_import_bundle_from_cassandra,
    extract_ip_assets_from_nodes as extract_cassandra_ip_assets_from_nodes,
    fetch_cassandra_nodes,
    import_bundle_via_pipeline as import_cassandra_bundle_via_pipeline,
    parse_contact_points,
)

router = APIRouter()


def _run_cassandra_connector_job(
    *,
    job_id: str,
    db_path: str,
    user_id: int | None,
    contact_points: list[str],
    port: int,
    username: Optional[str],
    password: Optional[str],
    use_tls: bool,
    insecure: bool,
    asset_type: str,
    project_name: Optional[str],
    tags: Optional[list[str]],
    note: Optional[str],
    include_cluster_name_tag: bool,
    timeout: int,
    mode: str,
) -> None:
    _update_connector_job(job_id, status="running")
    connection = db.connect(db_path)
    try:
        db.init_db(connection)
        actor = repository.get_user_by_id(connection, user_id) if user_id else None
        logs, warnings, import_warning_count, import_error_count = (
            _run_cassandra_connector(
                connection=connection,
                user=actor,
                contact_points=contact_points,
                port=port,
                username=username,
                password=password,
                use_tls=use_tls,
                insecure=insecure,
                asset_type=asset_type,
                project_name=project_name,
                tags=tags,
                note=note,
                include_cluster_name_tag=include_cluster_name_tag,
                timeout=timeout,
                dry_run=mode == "dry-run",
            )
        )
        final_logs, toast_messages = _finalize_job_logs(
            logs=logs,
            warnings=warnings,
            import_warning_count=import_warning_count,
            import_error_count=import_error_count,
        )
        for toast in toast_messages:
            toast["message"] = f"Cassandra {mode}: {toast['message']}"
        _update_connector_job(
            job_id,
            status="completed",
            logs=_redact_connector_logs(final_logs, password),
            toast_messages=toast_messages,
        )
    except CassandraConnectorError as exc:
        _update_connector_job(
            job_id,
            status="failed",
            logs=["Connector failed. Review server logs for details."],
            toast_messages=[
                {
                    "type": "error",
                    "message": "Cassandra connector execution failed.",
                }
            ],
        )
    finally:
        connection.close()


def _run_cassandra_connector(
    *,
    connection,
    user,
    contact_points: list[str],
    port: int,
    username: Optional[str],
    password: Optional[str],
    use_tls: bool,
    insecure: bool,
    asset_type: str,
    project_name: Optional[str],
    tags: Optional[list[str]],
    note: Optional[str],
    include_cluster_name_tag: bool,
    timeout: int,
    dry_run: bool,
) -> tuple[list[str], list[str], int, int]:
    logs: list[str] = []

    records = fetch_cassandra_nodes(
        contact_points=contact_points,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        insecure=insecure,
        timeout=timeout,
    )
    logs.append(
        f"Connected to Cassandra contact points '{', '.join(contact_points)}' on port {port}."
    )
    logs.append(f"Collected {len(records)} nodes from Cassandra metadata.")

    ip_assets, extraction_warnings = extract_cassandra_ip_assets_from_nodes(
        records,
        default_type=asset_type,
        project_name=project_name,
        tags=tags,
        note=note,
        include_cluster_name_tag=include_cluster_name_tag,
    )
    logs.append(f"Prepared {len(ip_assets)} IP assets from node metadata.")
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

    bundle, bundle_warnings = build_import_bundle_from_cassandra(ip_assets)
    result = import_cassandra_bundle_via_pipeline(
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


@router.post("/ui/connectors/cassandra/run", response_class=HTMLResponse)
async def ui_run_cassandra_connector(
    request: Request,
    background_tasks: BackgroundTasks,
    db_path: str = Depends(get_db_path),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    contact_points_raw = (form_data.get("contact_points") or "").strip()
    port_raw = (form_data.get("port") or "9042").strip()
    username_raw = (form_data.get("username") or "").strip()
    password_raw = form_data.get("password")
    use_tls = form_data.get("use_tls") == "1"
    insecure = form_data.get("insecure") == "1"
    asset_type_raw = (form_data.get("asset_type") or IPAssetType.OTHER.value).strip()
    project_name_raw = (form_data.get("project_name") or "").strip()
    tags_raw = (form_data.get("tags") or "").strip()
    note_raw = (form_data.get("note") or "").strip()
    include_cluster_name_tag = form_data.get("include_cluster_name_tag") == "1"
    mode = (form_data.get("mode") or "dry-run").strip().lower()
    timeout_raw = (form_data.get("timeout") or "30").strip()

    has_username = bool(username_raw)
    has_password = isinstance(password_raw, str) and len(password_raw) > 0

    errors: list[str] = []
    try:
        contact_points = parse_contact_points(contact_points_raw)
    except CassandraConnectorError as exc:
        errors.append(str(exc))
        contact_points = []

    try:
        port = int(port_raw)
        if port <= 0 or port > 65535:
            raise ValueError
    except ValueError:
        errors.append("Port must be a valid number between 1 and 65535.")
        port = 9042

    if mode not in {"dry-run", "apply"}:
        errors.append("Mode must be dry-run or apply.")

    if has_username and not has_password:
        errors.append("Password is required when username is provided.")
    elif has_password and not has_username:
        errors.append("Username is required when password is provided.")
    if insecure and not use_tls:
        errors.append("Insecure TLS requires TLS to be enabled.")

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
    note = note_raw or None
    username = username_raw or None
    password = password_raw if has_password else None

    form_state = {
        "contact_points": contact_points_raw,
        "port": str(port),
        "username": username_raw,
        "password": "",
        "use_tls": use_tls,
        "insecure": insecure,
        "asset_type": asset_type,
        "project_name": project_name_raw,
        "tags": tags_raw,
        "note": note_raw,
        "include_cluster_name_tag": include_cluster_name_tag,
        "mode": mode if mode in {"dry-run", "apply"} else "dry-run",
        "timeout": str(timeout),
    }
    if errors:
        return _render_template(
            request,
            "connectors_legacy.html",
            _connectors_context(
                active_tab="cassandra",
                cassandra_form_state=form_state,
                cassandra_errors=errors,
            ),
            active_nav="connectors",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if mode == "apply" and user.role != UserRole.EDITOR:
        return _render_template(
            request,
            "connectors_legacy.html",
            _connectors_context(
                active_tab="cassandra",
                cassandra_form_state=form_state,
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

    job_id = _create_connector_job(active_tab="cassandra", form_state=form_state)
    background_tasks.add_task(
        _run_cassandra_connector_job,
        job_id=job_id,
        db_path=db_path,
        user_id=int(user.id),
        contact_points=contact_points,
        port=port,
        username=username,
        password=password,
        use_tls=use_tls,
        insecure=insecure,
        asset_type=asset_type,
        project_name=project_name,
        tags=tags,
        note=note,
        include_cluster_name_tag=include_cluster_name_tag,
        timeout=timeout,
        mode=mode,
    )
    return RedirectResponse(
        url=f"/ui/connectors?tab=cassandra&job_id={job_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
