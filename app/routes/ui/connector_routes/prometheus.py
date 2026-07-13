from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db, repository
from app.dependencies import get_db_path
from app.models import IPAssetType, UserRole
from app.routes.ui.utils import _parse_form_data, _render_template, get_current_ui_user
from app.utils import split_tag_string
from .common import _finalize_job_logs
from .forms import _connectors_context
from .job_store import _create_connector_job, _update_connector_job

from app.connectors.prometheus import (
    PrometheusConnectorError,
    build_import_bundle_from_prometheus,
    extract_ip_assets_from_result,
    fetch_prometheus_query_result,
    import_bundle_via_pipeline as import_prometheus_bundle_via_pipeline,
)
from .prometheus_preview import _build_prometheus_dry_run_change_logs

router = APIRouter()


def _run_prometheus_connector_job(
    *,
    job_id: str,
    db_path: str,
    user_id: int | None,
    prometheus_url: str,
    query: str,
    ip_label: str,
    asset_type: str,
    project_name: Optional[str],
    tags: Optional[list[str]],
    token: Optional[str],
    insecure: bool,
    timeout: int,
    mode: str,
) -> None:
    _update_connector_job(job_id, status="running")
    connection = db.connect(db_path)
    try:
        db.init_db(connection)
        actor = repository.get_user_by_id(connection, user_id) if user_id else None
        logs, warnings, import_warning_count, import_error_count = (
            _run_prometheus_connector(
                connection=connection,
                user=actor,
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
        )
        final_logs, toast_messages = _finalize_job_logs(
            logs=logs,
            warnings=warnings,
            import_warning_count=import_warning_count,
            import_error_count=import_error_count,
        )
        for toast in toast_messages:
            toast["message"] = f"Prometheus {mode}: {toast['message']}"
        _update_connector_job(
            job_id,
            status="completed",
            logs=final_logs,
            toast_messages=toast_messages,
        )
    except PrometheusConnectorError as exc:
        _update_connector_job(
            job_id,
            status="failed",
            logs=[f"Connector failed: {exc}"],
            toast_messages=[
                {
                    "type": "error",
                    "message": "Prometheus connector execution failed.",
                }
            ],
        )
    finally:
        connection.close()


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


@router.post("/ui/connectors/prometheus/run", response_class=HTMLResponse)
async def ui_run_prometheus_connector(
    request: Request,
    background_tasks: BackgroundTasks,
    db_path: str = Depends(get_db_path),
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

    job_id = _create_connector_job(active_tab="prometheus", form_state=form_state)
    background_tasks.add_task(
        _run_prometheus_connector_job,
        job_id=job_id,
        db_path=db_path,
        user_id=int(user.id),
        prometheus_url=prometheus_url,
        query=query,
        ip_label=ip_label,
        asset_type=asset_type,
        project_name=project_name,
        tags=tags,
        token=token,
        insecure=insecure,
        timeout=timeout,
        mode=mode,
    )
    return RedirectResponse(
        url=f"/ui/connectors?tab=prometheus&job_id={job_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
