from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db, repository
from app.dependencies import get_db_path
from app.models import UserRole
from app.routes.ui.utils import _parse_form_data, _render_template, get_current_ui_user
from .common import _finalize_job_logs, _redact_connector_logs
from .forms import _connectors_context
from .job_store import _create_connector_job, _update_connector_job

from app.connectors.vcenter import (
    VCenterConnectorError,
    build_import_bundle,
    fetch_vcenter_inventory,
    import_bundle_via_pipeline as import_vcenter_bundle_via_pipeline,
)

router = APIRouter()


def _run_vcenter_connector_job(
    *,
    job_id: str,
    db_path: str,
    user_id: int | None,
    server: str,
    username: str,
    password: str,
    port: int,
    insecure: bool,
    mode: str,
) -> None:
    _update_connector_job(job_id, status="running")
    connection = db.connect(db_path)
    try:
        db.init_db(connection)
        actor = repository.get_user_by_id(connection, user_id) if user_id else None
        logs, warnings, import_warning_count, import_error_count = (
            _run_vcenter_connector(
                connection=connection,
                user=actor,
                server=server,
                username=username,
                password=password,
                port=port,
                insecure=insecure,
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
            toast["message"] = f"vCenter {mode}: {toast['message']}"
        _update_connector_job(
            job_id,
            status="completed",
            logs=_redact_connector_logs(final_logs, password),
            toast_messages=toast_messages,
        )
    except VCenterConnectorError as exc:
        _update_connector_job(
            job_id,
            status="failed",
            logs=["Connector failed. Review server logs for details."],
            toast_messages=[
                {
                    "type": "error",
                    "message": "vCenter connector execution failed.",
                }
            ],
        )
    finally:
        connection.close()


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


@router.post("/ui/connectors/vcenter/run", response_class=HTMLResponse)
async def ui_run_vcenter_connector(
    request: Request,
    background_tasks: BackgroundTasks,
    db_path: str = Depends(get_db_path),
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
            "connectors_legacy.html",
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
            "connectors_legacy.html",
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

    job_id = _create_connector_job(active_tab="vcenter", form_state=form_state)
    background_tasks.add_task(
        _run_vcenter_connector_job,
        job_id=job_id,
        db_path=db_path,
        user_id=int(user.id),
        server=server,
        username=username,
        password=password,
        port=port,
        insecure=insecure,
        mode=mode,
    )
    return RedirectResponse(
        url=f"/ui/connectors?tab=vcenter&job_id={job_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
