from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse

from app.connectors.vcenter import (
    VCenterConnectorError,
    build_import_bundle,
    fetch_vcenter_inventory,
)
from app.dependencies import get_connection
from app.imports import BundleImporter, run_import
from app.models import UserRole
from .utils import _render_template
from .utils import _parse_form_data, get_current_ui_user

router = APIRouter()


def _default_vcenter_form_state() -> dict[str, object]:
    return {
        "server": "",
        "username": "",
        "password": "",
        "port": "443",
        "insecure": False,
        "mode": "dry-run",
    }


def _connectors_context(
    *,
    active_tab: str = "overview",
    vcenter_form_state: Optional[dict[str, object]] = None,
    vcenter_errors: Optional[list[str]] = None,
    vcenter_logs: Optional[list[str]] = None,
    toast_messages: Optional[list[dict[str, str]]] = None,
) -> dict[str, object]:
    return {
        "title": "ipocket - Connectors",
        "active_tab": active_tab,
        "vcenter_form_state": vcenter_form_state or _default_vcenter_form_state(),
        "vcenter_errors": vcenter_errors or [],
        "vcenter_logs": vcenter_logs or [],
        "toast_messages": toast_messages or [],
    }


@router.get("/ui/connectors", response_class=HTMLResponse)
def ui_connectors(
    request: Request,
    tab: Optional[str] = Query(default=None),
) -> HTMLResponse:
    active_tab = "vcenter" if tab == "vcenter" else "overview"
    return _render_template(
        request,
        "connectors.html",
        _connectors_context(active_tab=active_tab),
        active_nav="connectors",
    )


def _run_vcenter_connector(
    *,
    connection,
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

    bundle_payload = json.dumps(bundle).encode("utf-8")
    result = run_import(
        connection,
        BundleImporter(),
        {"bundle": bundle_payload},
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
