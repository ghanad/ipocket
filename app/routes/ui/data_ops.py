from __future__ import annotations

import json

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import exports
from app.dependencies import get_connection
from app.imports import BundleImporter, CsvImporter, run_import
from app.imports.models import ImportApplyResult, ImportSummary
from app.imports.nmap import NmapImportResult, import_nmap_xml
from app.models import UserRole
from .utils import (
    _build_csv_content,
    _csv_response,
    _format_ip_asset_csv_rows,
    _json_response,
    _normalize_export_asset_type,
    _parse_multipart_form,
    _render_template,
    _zip_response,
    get_current_ui_user,
)

router = APIRouter()

def _data_ops_context(
    *,
    active_tab: str = "import",
    **overrides: object,
) -> dict[str, object]:
    context: dict[str, object] = {
        "title": "ipocket - Data Operations",
        "active_tab": active_tab,
        "bundle_result": None,
        "csv_result": None,
        "nmap_result": None,
        "errors": [],
        "nmap_errors": [],
    }
    context.update(overrides)
    return context


def _render_data_ops_template(
    request: Request,
    *,
    active_tab: str = "import",
    status_code: int = status.HTTP_200_OK,
    **overrides: object,
) -> HTMLResponse:
    return _render_template(
        request,
        "data_ops.html",
        _data_ops_context(active_tab=active_tab, **overrides),
        active_nav="data-ops",
        status_code=status_code,
    )


@router.get("/ui/export", response_class=HTMLResponse)
def ui_export(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_data_ops_template(request, active_tab="export")

def _summary_payload(summary: ImportSummary) -> dict[str, dict[str, int]]:
    return {
        "vendors": summary.vendors.__dict__,
        "projects": summary.projects.__dict__,
        "hosts": summary.hosts.__dict__,
        "ip_assets": summary.ip_assets.__dict__,
        "total": summary.total().__dict__,
    }

def _import_result_payload(result: ImportApplyResult) -> dict[str, object]:
    return {
        "summary": _summary_payload(result.summary),
        "errors": [issue.__dict__ for issue in result.errors],
        "warnings": [issue.__dict__ for issue in result.warnings],
    }

def _nmap_result_payload(result: NmapImportResult) -> dict[str, object]:
    return {
        "discovered_up_hosts": result.discovered_up_hosts,
        "new_ips_created": result.new_ips_created,
        "existing_ips_seen": result.existing_ips_seen,
        "errors": result.errors,
        "new_assets": [asset.__dict__ for asset in result.new_assets],
    }

@router.get("/ui/import", response_class=HTMLResponse)
def ui_import(
    request: Request,
    tab: Optional[str] = Query(default=None),
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    active_tab = "export" if tab == "export" else "import"
    return _render_data_ops_template(request, active_tab=active_tab)

@router.get("/ui/import-nmap", response_class=HTMLResponse)
def ui_import_nmap(
    _request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return RedirectResponse(url="/ui/import", status_code=302)

@router.post("/ui/import/nmap", response_class=HTMLResponse)
@router.post("/ui/import-nmap", response_class=HTMLResponse)
async def ui_import_nmap_submit(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_multipart_form(request)
    mode = form_data.get("mode")
    if mode is None:
        # Backward compatibility: old Nmap form used a dry_run checkbox.
        # If missing, treat as apply (same as historical behavior).
        dry_run = bool(form_data.get("dry_run"))
    else:
        dry_run = mode != "apply"
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    upload = form_data.get("nmap_file")
    if upload is None:
        return _render_data_ops_template(
            request,
            active_tab="import",
            nmap_errors=["Nmap XML file is required."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    payload = await upload.read()
    if not payload:
        return _render_data_ops_template(
            request,
            active_tab="import",
            nmap_errors=["Nmap XML file is empty."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = import_nmap_xml(connection, payload, dry_run=dry_run, current_user=user)
    toast_messages = []
    if not dry_run:
        if result.errors:
            toast_messages.append({"type": "error", "message": "Nmap import completed with errors."})
        else:
            toast_messages.append({"type": "success", "message": "Nmap import applied successfully."})
    return _render_data_ops_template(
        request,
        active_tab="import",
        nmap_result=_nmap_result_payload(result),
        toast_messages=toast_messages,
    )

@router.post("/ui/import/bundle", response_class=HTMLResponse)
async def ui_import_bundle(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_multipart_form(request)
    mode = form_data.get("mode", "dry-run")
    dry_run = mode != "apply"
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    upload = form_data.get("bundle_file")
    if upload is None:
        return _render_data_ops_template(
            request,
            active_tab="import",
            errors=["bundle.json file is required."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    payload = await upload.read()
    result = run_import(connection, BundleImporter(), {"bundle": payload}, dry_run=dry_run)
    toast_messages = []
    if not dry_run:
        if result.errors:
            toast_messages.append({"type": "error", "message": "Bundle import completed with errors."})
        else:
            toast_messages.append({"type": "success", "message": "Bundle import applied successfully."})
    return _render_data_ops_template(
        request,
        active_tab="import",
        bundle_result=_import_result_payload(result),
        toast_messages=toast_messages,
    )

@router.post("/ui/import/csv", response_class=HTMLResponse)
async def ui_import_csv(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> HTMLResponse:
    form_data = await _parse_multipart_form(request)
    mode = form_data.get("mode", "dry-run")
    dry_run = mode != "apply"
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    hosts_file = form_data.get("hosts_file")
    ip_assets_file = form_data.get("ip_assets_file")
    if hosts_file is None and ip_assets_file is None:
        return _render_data_ops_template(
            request,
            active_tab="import",
            errors=["Upload at least one CSV file (hosts.csv or ip-assets.csv)."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    inputs: dict[str, bytes] = {}
    if hosts_file is not None:
        hosts_payload = await hosts_file.read()
        if hosts_payload:
            inputs["hosts"] = hosts_payload
    if ip_assets_file is not None:
        ip_assets_payload = await ip_assets_file.read()
        if ip_assets_payload:
            inputs["ip_assets"] = ip_assets_payload
    if not inputs:
        return _render_data_ops_template(
            request,
            active_tab="import",
            errors=["Upload at least one non-empty CSV file (hosts.csv or ip-assets.csv)."],
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = run_import(connection, CsvImporter(), inputs, dry_run=dry_run)
    toast_messages = []
    if not dry_run:
        if result.errors:
            toast_messages.append({"type": "error", "message": "CSV import completed with errors."})
        else:
            toast_messages.append({"type": "success", "message": "CSV import applied successfully."})
    return _render_data_ops_template(
        request,
        active_tab="import",
        csv_result=_import_result_payload(result),
        toast_messages=toast_messages,
    )

@router.get("/export/ip-assets.csv")
def export_ip_assets_csv(
    include_archived: bool = Query(default=False),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    project: Optional[str] = Query(default=None),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_ip_assets(
        connection,
        include_archived=include_archived,
        asset_type=_normalize_export_asset_type(asset_type),
        project_name=project,
        host_name=host,
    )
    headers = [
        "ip_address",
        "type",
        "project_name",
        "host_name",
        "tags",
        "notes",
        "archived",
        "created_at",
        "updated_at",
    ]
    return _csv_response("ip-assets.csv", headers, _format_ip_asset_csv_rows(export_rows))

@router.get("/export/ip-assets.json")
def export_ip_assets_json(
    include_archived: bool = Query(default=False),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    project: Optional[str] = Query(default=None),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_ip_assets(
        connection,
        include_archived=include_archived,
        asset_type=_normalize_export_asset_type(asset_type),
        project_name=project,
        host_name=host,
    )
    return _json_response("ip-assets.json", export_rows)

@router.get("/export/hosts.csv")
def export_hosts_csv(
    include_archived: bool = Query(default=False),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_hosts(connection, host_name=host)
    headers = ["name", "notes", "vendor_name"]
    return _csv_response("hosts.csv", headers, export_rows)

@router.get("/export/hosts.json")
def export_hosts_json(
    include_archived: bool = Query(default=False),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_hosts(connection, host_name=host)
    return _json_response("hosts.json", export_rows)

@router.get("/export/vendors.csv")
def export_vendors_csv(
    include_archived: bool = Query(default=False),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_vendors(connection)
    headers = ["name"]
    return _csv_response("vendors.csv", headers, export_rows)

@router.get("/export/vendors.json")
def export_vendors_json(
    include_archived: bool = Query(default=False),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_vendors(connection)
    return _json_response("vendors.json", export_rows)

@router.get("/export/projects.csv")
def export_projects_csv(
    include_archived: bool = Query(default=False),
    project: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_projects(connection, project_name=project)
    headers = ["name", "description", "color"]
    return _csv_response("projects.csv", headers, export_rows)

@router.get("/export/projects.json")
def export_projects_json(
    include_archived: bool = Query(default=False),
    project: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    export_rows = exports.export_projects(connection, project_name=project)
    return _json_response("projects.json", export_rows)

@router.get("/export/bundle.json")
def export_bundle_json(
    include_archived: bool = Query(default=False),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    project: Optional[str] = Query(default=None),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    normalized_type = _normalize_export_asset_type(asset_type)
    bundle = exports.export_bundle(
        connection,
        include_archived=include_archived,
        asset_type=normalized_type,
        project_name=project,
        host_name=host,
    )
    return _json_response("bundle.json", bundle)

@router.get("/export/bundle.zip")
def export_bundle_zip(
    include_archived: bool = Query(default=False),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    project: Optional[str] = Query(default=None),
    host: Optional[str] = Query(default=None),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
) -> Response:
    normalized_type = _normalize_export_asset_type(asset_type)
    ip_assets = exports.export_ip_assets(
        connection,
        include_archived=include_archived,
        asset_type=normalized_type,
        project_name=project,
        host_name=host,
    )
    projects = exports.export_projects(connection, project_name=project)
    hosts = exports.export_hosts(connection, host_name=host)
    vendors = exports.export_vendors(connection)
    bundle = exports.export_bundle(
        connection,
        include_archived=include_archived,
        asset_type=normalized_type,
        project_name=project,
        host_name=host,
    )
    files = {
        "bundle.json": json.dumps(bundle),
        "ip-assets.csv": _build_csv_content(
            [
                "ip_address",
                "type",
                "project_name",
                "host_name",
                "tags",
                "notes",
                "archived",
                "created_at",
                "updated_at",
            ],
            _format_ip_asset_csv_rows(ip_assets),
        ),
        "projects.csv": _build_csv_content(["name", "description", "color"], projects),
        "hosts.csv": _build_csv_content(["name", "notes", "vendor_name"], hosts),
        "vendors.csv": _build_csv_content(["name"], vendors),
    }
    return _zip_response("bundle.zip", files)
