from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import secrets
import sqlite3
import zipfile
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import auth, build_info, exports, repository
from app.environment import use_local_assets
from app.dependencies import get_connection
from app.imports import BundleImporter, CsvImporter, run_import
from app.imports.nmap import NmapImportResult, import_nmap_xml
from app.imports.models import ImportApplyResult, ImportSummary
from app.models import IPAsset, IPAssetType, UserRole
from app.utils import (
    DEFAULT_PROJECT_COLOR,
    DEFAULT_TAG_COLOR,
    normalize_cidr,
    normalize_hex_color,
    normalize_tag_name,
    normalize_tag_names,
    split_tag_string,
    validate_ip_address,
)

router = APIRouter()

SESSION_COOKIE = "ipocket_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret").encode("utf-8")
FLASH_COOKIE = "ipocket_flash"
FLASH_ALLOWED_TYPES = {"success", "info", "error", "warning"}
FLASH_MAX_MESSAGES = 5


def _is_auto_host_for_bmc_enabled() -> bool:
    return os.getenv("IPOCKET_AUTO_HOST_FOR_BMC", "1").strip().lower() not in {"0", "false", "no", "off"}


def _render_template(
    request: Request,
    template_name: str,
    context: dict,
    status_code: int = 200,
    show_nav: bool = True,
    active_nav: str = "",
) -> HTMLResponse:
    templates = request.app.state.templates
    is_authenticated = _is_authenticated_request(request)
    flash_messages = _load_flash_messages(request)
    toast_messages = list(flash_messages)
    extra_toasts = context.pop("toast_messages", None)
    if extra_toasts:
        toast_messages.extend(extra_toasts)
    payload = {
        "request": request,
        "show_nav": show_nav,
        "active_nav": active_nav,
        "use_local_assets": use_local_assets(),
        "is_authenticated": is_authenticated,
        "build_info": build_info.get_display_build_info() if is_authenticated else None,
        "toast_messages": toast_messages,
        **context,
    }
    if templates is None:
        return _render_fallback_template(
            template_name, payload, status_code=status_code
        )
    response = templates.TemplateResponse(
        template_name, payload, status_code=status_code
    )
    if flash_messages:
        response.delete_cookie(FLASH_COOKIE)
    return response


def _append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query[key] = [value]
    updated_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=updated_query))


def _render_fallback_template(
    template_name: str, payload: dict, status_code: int = 200
) -> HTMLResponse:
    lines = []
    if not payload.get("use_local_assets", True):
        lines.extend(
            [
                '<link rel="preconnect" href="https://fonts.googleapis.com" />',
                '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
                (
                    '<link rel="stylesheet" '
                    'href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" />'
                ),
            ]
        )
    lines.append('<link rel="stylesheet" href="/static/app.css" />')
    if payload.get("use_local_assets", True):
        lines.append('<script src="/static/vendor/htmx.min.js" defer></script>')
    else:
        lines.append('<script src="https://unpkg.com/htmx.org@1.9.12" defer></script>')
    lines.append(str(payload.get("title", "ipocket")))
    assets = payload.get("assets") or []
    for asset in assets:
        ip_address = asset.get("ip_address")
        if ip_address:
            lines.append(str(ip_address))
        if asset.get("project_unassigned"):
            lines.append("Unassigned")
    for project in payload.get("projects") or []:
        name = getattr(project, "name", None)
        if name:
            lines.append(str(name))
    for host in payload.get("hosts") or []:
        name = getattr(host, "name", None) if not isinstance(host, dict) else host.get("name")
        if name:
            lines.append(str(name))
    for vendor in payload.get("vendors") or []:
        name = getattr(vendor, "name", None) if not isinstance(vendor, dict) else vendor.get("name")
        if name:
            lines.append(str(name))
    if template_name == "management.html":
        summary = payload.get("summary") or {}
        for key in ("active_ip_total", "archived_ip_total", "host_total", "vendor_total", "project_total"):
            if key in summary:
                lines.append(str(summary[key]))
        for report in payload.get("utilization") or []:
            used = report.get("used") if isinstance(report, dict) else None
            if used is not None:
                lines.append(str(used))
    if template_name == "ranges.html":
        for ip_range in payload.get("ranges") or []:
            cidr = getattr(ip_range, "cidr", None)
            if cidr:
                lines.append(str(cidr))
    for error in payload.get("errors") or []:
        lines.append(str(error))
    if template_name == "login.html":
        lines.append("Login")
    build = payload.get("build_info")
    if payload.get("show_nav") and build:
        version = build.get("version", "dev")
        commit = build.get("commit", "unknown")
        build_time = build.get("build_time", "unknown")
        lines.append(f"ipocket v{version} ({commit}) • built {build_time}")
    return HTMLResponse(content="\n".join(lines), status_code=status_code)


def _sign_session_value(value: str) -> str:
    signature = hmac.new(
        SESSION_SECRET, value.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{value}.{signature}"


def _verify_session_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if "." not in value:
        return None
    payload, signature = value.rsplit(".", 1)
    expected = hmac.new(
        SESSION_SECRET, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return None
    return payload


def _normalize_flash_type(value: Optional[str]) -> str:
    if not value:
        return "info"
    normalized = value.strip().lower()
    if normalized in FLASH_ALLOWED_TYPES:
        return normalized
    return "info"


def _encode_flash_payload(messages: list[dict[str, str]]) -> str:
    serialized = json.dumps(messages, separators=(",", ":"))
    return base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("utf-8")


def _decode_flash_payload(payload: str) -> Optional[str]:
    try:
        return base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None


def _load_flash_messages(request: Request) -> list[dict[str, str]]:
    signed_value = request.cookies.get(FLASH_COOKIE)
    payload = _verify_session_value(signed_value)
    if not payload:
        return []
    decoded = _decode_flash_payload(payload)
    if decoded is None:
        return []
    try:
        data = json.loads(decoded)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    messages: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        if not message:
            continue
        messages.append(
            {
                "type": _normalize_flash_type(item.get("type")),
                "message": message,
            }
        )
    return messages[:FLASH_MAX_MESSAGES]


def _store_flash_messages(response: Response, messages: list[dict[str, str]]) -> None:
    if not messages:
        return
    payload = _encode_flash_payload(messages[:FLASH_MAX_MESSAGES])
    response.set_cookie(
        FLASH_COOKIE,
        _sign_session_value(payload),
        httponly=True,
        samesite="lax",
    )


def _add_flash_message(
    request: Request,
    response: Response,
    message_type: str,
    message: str,
) -> None:
    messages = _load_flash_messages(request)
    messages.append(
        {
            "type": _normalize_flash_type(message_type),
            "message": message,
        }
    )
    _store_flash_messages(response, messages)


def _redirect_with_flash(
    request: Request,
    url: str,
    message: str,
    message_type: str = "success",
    status_code: int = 303,
) -> RedirectResponse:
    response = RedirectResponse(url=url, status_code=status_code)
    _add_flash_message(request, response, message_type, message)
    return response


def _is_authenticated_request(request: Request) -> bool:
    signed_session = request.cookies.get(SESSION_COOKIE)
    return _verify_session_value(signed_session) is not None


def get_current_ui_user(
    request: Request, connection=Depends(get_connection)
):
    signed_session = request.cookies.get(SESSION_COOKIE)
    user_id = _verify_session_value(signed_session)
    if not user_id:
        current_path = request.url.path
        query = request.url.query
        return_url = current_path
        if query:
            return_url = f"{current_path}?{query}"
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/ui/login?return_to={return_url}"},
        )
    user = repository.get_user_by_id(connection, int(user_id))
    if user is None or not user.is_active:
        current_path = request.url.path
        query = request.url.query
        return_url = current_path
        if query:
            return_url = f"{current_path}?{query}"
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/ui/login?return_to={return_url}"},
        )
    return user


def require_ui_editor(user=Depends(get_current_ui_user)):
    if user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def _is_unassigned(project_id: Optional[int]) -> bool:
    return project_id is None


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _parse_optional_int_query(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _parse_positive_int_query(value: Optional[str], default: int) -> int:
    parsed = _parse_optional_int_query(value)
    if parsed is None or parsed <= 0:
        return default
    return parsed


def _parse_inline_ip_list(value: Optional[str]) -> list[str]:
    normalized = _parse_optional_str(value)
    if normalized is None:
        return []
    parts = re.split(r"[,\s]+", normalized)
    seen: set[str] = set()
    entries: list[str] = []
    for part in parts:
        candidate = part.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        entries.append(candidate)
    return entries


def _collect_inline_ip_errors(
    connection: sqlite3.Connection,
    host_id: Optional[int],
    os_ips: list[str],
    bmc_ips: list[str],
) -> tuple[list[str], list[tuple[str, IPAssetType]], list[tuple[str, IPAssetType]]]:
    """Collect errors and categorize IPs for creation or update.
    
    Returns:
        A tuple of (errors, ips_to_create, ips_to_update) where:
        - errors: List of error messages
        - ips_to_create: List of (ip_address, asset_type) for new IPs
        - ips_to_update: List of (ip_address, asset_type) for existing IPs to link to host
    """
    errors: list[str] = []
    to_create: list[tuple[str, IPAssetType]] = []
    to_update: list[tuple[str, IPAssetType]] = []
    conflict_ips = set(os_ips) & set(bmc_ips)
    if conflict_ips:
        for ip in sorted(conflict_ips):
            errors.append(f"IP address appears in both OS and BMC fields: {ip}.")
    os_queue = [ip for ip in os_ips if ip not in conflict_ips]
    bmc_queue = [ip for ip in bmc_ips if ip not in conflict_ips]
    for ip_address, asset_type in [
        *[(ip, IPAssetType.OS) for ip in os_queue],
        *[(ip, IPAssetType.BMC) for ip in bmc_queue],
    ]:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(f"{exc.detail} ({ip_address})")
            continue
        existing = repository.get_ip_asset_by_ip(connection, ip_address)
        if existing is not None:
            # Already linked to this host with same type - skip
            if host_id is not None and existing.host_id == host_id and existing.asset_type == asset_type:
                continue
            # Existing IP - add to update list to link to host
            to_update.append((ip_address, asset_type))
            continue
        to_create.append((ip_address, asset_type))
    deduped_errors = list(dict.fromkeys(errors))
    return deduped_errors, to_create, to_update


def _normalize_project_color(value: Optional[str]) -> Optional[str]:
    normalized_value = _parse_optional_str(value)
    if normalized_value is None:
        return None
    return normalize_hex_color(normalized_value)


def _normalize_assignment_filter(value: Optional[str]) -> str:
    if value == "project":
        return value
    return "project"


def _normalize_asset_type(value: Optional[str]) -> Optional[IPAssetType]:
    normalized_value = _parse_optional_str(value)
    if normalized_value is None:
        return None
    return IPAssetType.normalize(normalized_value)


def _normalize_export_asset_type(value: Optional[str]) -> Optional[IPAssetType]:
    if value is None:
        return None
    try:
        return IPAssetType.normalize(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid asset type. Use VM, OS, BMC (formerly IPMI/iLO), VIP, OTHER.",
        ) from exc


def _build_csv_content(headers: list[str], rows: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in headers})
    return buffer.getvalue()


def _format_ip_asset_csv_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    formatted: list[dict[str, object]] = []
    for row in rows:
        updated = dict(row)
        tags = updated.get("tags")
        if isinstance(tags, list):
            updated["tags"] = ", ".join(tags)
        formatted.append(updated)
    return formatted


def _csv_response(filename: str, headers: list[str], rows: list[dict[str, object]]) -> Response:
    response = Response(content=_build_csv_content(headers, rows), media_type="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _json_response(filename: str, payload: object) -> Response:
    response = JSONResponse(content=payload)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _zip_response(filename: str, files: dict[str, str]) -> Response:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files.items():
            archive.writestr(file_name, content)
    response = Response(content=buffer.getvalue(), media_type="application/zip")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_asset_view_models(
    assets: list[IPAsset],
    project_lookup: dict[int, dict[str, Optional[str]]],
    host_lookup: dict[int, str],
    tag_lookup: dict[int, list[dict[str, str]]],
    host_pair_lookup: Optional[dict[int, dict[str, list[str]]]] = None,
) -> list[dict]:
    view_models = []
    host_pair_lookup = host_pair_lookup or {}
    for asset in assets:
        project = project_lookup.get(asset.project_id) if asset.project_id else None
        project_name = project.get("name") if project else ""
        project_color = project.get("color") if project else None
        project_unassigned = not project_name
        host_name = host_lookup.get(asset.host_id) if asset.host_id else ""
        tags = tag_lookup.get(asset.id, [])
        tags_value = ", ".join(tag["name"] for tag in tags)
        host_pair = ""
        if asset.host_id and asset.asset_type in (IPAssetType.OS, IPAssetType.BMC):
            pair_type = IPAssetType.BMC.value if asset.asset_type == IPAssetType.OS else IPAssetType.OS.value
            pair_ips = host_pair_lookup.get(asset.host_id, {}).get(pair_type, [])
            host_pair = ", ".join(pair_ips)
        view_models.append(
            {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "type": asset.asset_type.value,
                "project_id": asset.project_id or "",
                "project_name": project_name,
                "project_color": project_color,
                "host_id": asset.host_id or "",
                "notes": asset.notes or "",
                "host_name": host_name,
                "tags": tags,
                "tags_value": tags_value,
                "host_pair": host_pair,
                "unassigned": _is_unassigned(asset.project_id),
                "project_unassigned": project_unassigned,
            }
        )
    return view_models


async def _parse_form_data(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode())
    return {key: values[0] for key, values in parsed.items()}


async def _parse_multipart_form(request: Request) -> dict:
    form = await request.form()
    return dict(form)


@router.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return RedirectResponse(url="/ui/ip-assets")


@router.get("/ui/about", response_class=HTMLResponse)
def ui_about(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "about.html",
        {"title": "ipocket - About"},
        active_nav="",
    )


@router.get("/ui/management", response_class=HTMLResponse)
def ui_management(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    summary = repository.get_management_summary(connection)
    utilization = repository.get_ip_range_utilization(connection)
    return _render_template(
        request,
        "management.html",
        {"title": "ipocket - Management Overview", "summary": summary, "utilization": utilization},
        active_nav="management",
    )


@router.get("/ui/export", response_class=HTMLResponse)
def ui_export(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "export.html",
        {"title": "ipocket - Export"},
        active_nav="export",
    )


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
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": None,
            "nmap_result": None,
            "errors": [],
            "nmap_errors": [],
        },
        active_nav="import",
    )


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
    dry_run = bool(form_data.get("dry_run"))
    if not dry_run and user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    upload = form_data.get("nmap_file")
    if upload is None:
        return _render_template(
            request,
            "import.html",
            {
                "title": "ipocket - Import",
                "bundle_result": None,
                "csv_result": None,
                "nmap_result": None,
                "errors": [],
                "nmap_errors": ["Nmap XML file is required."],
            },
            active_nav="import",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    payload = await upload.read()
    if not payload:
        return _render_template(
            request,
            "import.html",
            {
                "title": "ipocket - Import",
                "bundle_result": None,
                "csv_result": None,
                "nmap_result": None,
                "errors": [],
                "nmap_errors": ["Nmap XML file is empty."],
            },
            active_nav="import",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = import_nmap_xml(connection, payload, dry_run=dry_run, current_user=user)
    toast_messages = []
    if not dry_run:
        if result.errors:
            toast_messages.append({"type": "error", "message": "Nmap import completed with errors."})
        else:
            toast_messages.append({"type": "success", "message": "Nmap import applied successfully."})
    return _render_template(
        request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": None,
            "nmap_result": _nmap_result_payload(result),
            "errors": [],
            "nmap_errors": [],
            "toast_messages": toast_messages,
        },
        active_nav="import",
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
        return _render_template(
            request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": None,
            "nmap_result": None,
            "errors": ["bundle.json file is required."],
            "nmap_errors": [],
        },
        active_nav="import",
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
    return _render_template(
        request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": _import_result_payload(result),
            "csv_result": None,
            "nmap_result": None,
            "errors": [],
            "nmap_errors": [],
            "toast_messages": toast_messages,
        },
        active_nav="import",
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
        return _render_template(
            request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": None,
            "nmap_result": None,
            "errors": ["Upload at least one CSV file (hosts.csv or ip-assets.csv)."],
            "nmap_errors": [],
        },
        active_nav="import",
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
        return _render_template(
            request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": None,
            "nmap_result": None,
            "errors": ["Upload at least one non-empty CSV file (hosts.csv or ip-assets.csv)."],
            "nmap_errors": [],
        },
        active_nav="import",
        status_code=status.HTTP_400_BAD_REQUEST,
    )
    result = run_import(connection, CsvImporter(), inputs, dry_run=dry_run)
    toast_messages = []
    if not dry_run:
        if result.errors:
            toast_messages.append({"type": "error", "message": "CSV import completed with errors."})
        else:
            toast_messages.append({"type": "success", "message": "CSV import applied successfully."})
    return _render_template(
        request,
        "import.html",
        {
            "title": "ipocket - Import",
            "bundle_result": None,
            "csv_result": _import_result_payload(result),
            "nmap_result": None,
            "errors": [],
            "nmap_errors": [],
            "toast_messages": toast_messages,
        },
        active_nav="import",
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


@router.get("/ui/login", response_class=HTMLResponse)
def ui_login_form(request: Request, return_to: Optional[str] = None) -> HTMLResponse:
    return _render_template(
        request,
        "login.html",
        {"title": "ipocket - Login", "error_message": "", "return_to": return_to or ""},
        show_nav=False,
    )


@router.post("/ui/login", response_class=HTMLResponse)
async def ui_login_submit(
    request: Request, connection=Depends(get_connection)
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""
    return_to = form_data.get("return_to") or "/ui/ip-assets"

    user = None
    if username:
        user = repository.get_user_by_username(connection, username)
    if (
        user is None
        or not user.is_active
        or not auth.verify_password(password, user.hashed_password)
    ):
        return _render_template(
            request,
            "login.html",
            {
                "title": "ipocket - Login",
                "error_message": "Invalid username or password.",
                "return_to": return_to,
            },
            status_code=401,
            show_nav=False,
        )

    response = _redirect_with_flash(
        request,
        return_to,
        "Login successful.",
        message_type="success",
        status_code=303,
    )
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session_value(str(user.id)),
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/ui/logout")
def ui_logout(request: Request) -> Response:
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/ui/projects", response_class=HTMLResponse)
def ui_list_projects(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    projects = list(repository.list_projects(connection))
    return _render_template(
        request,
        "projects.html",
        {
            "title": "ipocket - Projects",
            "projects": projects,
            "errors": [],
            "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
        },
        active_nav="projects",
    )


@router.post("/ui/projects/{project_id}/edit", response_class=HTMLResponse)
async def ui_update_project(
    project_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    errors = []
    if not name:
        errors.append("Project name is required.")

    normalized_color = None
    if not errors:
        try:
            normalized_color = _normalize_project_color(color) or DEFAULT_PROJECT_COLOR
        except ValueError:
            errors.append("Project color must be a valid hex color (example: #1a2b3c).")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
            },
            status_code=400,
            active_nav="projects",
        )

    try:
        updated = repository.update_project(
            connection,
            project_id=project_id,
            name=name,
            description=description,
            color=normalized_color,
        )
    except sqlite3.IntegrityError:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": ["Project name already exists."],
                "form_state": {"name": "", "description": "", "color": DEFAULT_PROJECT_COLOR},
            },
            status_code=409,
            active_nav="projects",
        )

    if updated is None:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project updated.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/projects", response_class=HTMLResponse)
async def ui_create_project(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))
    color = form_data.get("color")

    errors = []
    if not name:
        errors.append("Project name is required.")

    normalized_color = None
    if not errors:
        try:
            normalized_color = _normalize_project_color(color) or DEFAULT_PROJECT_COLOR
        except ValueError:
            errors.append("Project color must be a valid hex color (example: #1a2b3c).")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
            },
            status_code=400,
            active_nav="projects",
        )

    try:
        repository.create_project(connection, name=name, description=description, color=normalized_color)
    except sqlite3.IntegrityError:
        errors.append("Project name already exists.")
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": name, "description": description or "", "color": color or DEFAULT_PROJECT_COLOR},
            },
            status_code=409,
            active_nav="projects",
        )

    return _redirect_with_flash(
        request,
        "/ui/projects",
        "Project created.",
        message_type="success",
        status_code=303,
    )


@router.get("/ui/tags", response_class=HTMLResponse)
def ui_list_tags(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    tags = list(repository.list_tags(connection))
    return _render_template(
        request,
        "tags.html",
        {
            "title": "ipocket - Tags",
            "tags": tags,
            "errors": [],
            "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
        },
        active_nav="tags",
    )


@router.post("/ui/tags", response_class=HTMLResponse)
async def ui_create_tag(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    errors = []
    normalized_name = ""
    if not name:
        errors.append("Tag name is required.")
    else:
        try:
            normalized_name = normalize_tag_name(name)
        except ValueError as exc:
            errors.append(str(exc))

    normalized_color = None
    if not errors:
        try:
            normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
        except ValueError:
            errors.append("Tag color must be a valid hex color (example: #1a2b3c).")

    if errors:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": errors,
                "form_state": {"name": name, "color": color or DEFAULT_TAG_COLOR},
            },
            status_code=400,
            active_nav="tags",
        )

    try:
        repository.create_tag(connection, name=normalized_name, color=normalized_color)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": ["Tag name already exists."],
                "form_state": {"name": name, "color": color or DEFAULT_TAG_COLOR},
            },
            status_code=409,
            active_nav="tags",
        )

    return RedirectResponse(url="/ui/tags", status_code=303)


@router.post("/ui/tags/{tag_id}/edit", response_class=HTMLResponse)
async def ui_edit_tag(
    tag_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    color = form_data.get("color")

    errors = []
    normalized_name = ""
    if not name:
        errors.append("Tag name is required.")
    else:
        try:
            normalized_name = normalize_tag_name(name)
        except ValueError as exc:
            errors.append(str(exc))

    normalized_color = None
    if not errors:
        try:
            normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
        except ValueError:
            errors.append("Tag color must be a valid hex color (example: #1a2b3c).")

    if errors:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": errors,
                "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
            },
            status_code=400,
            active_nav="tags",
        )

    try:
        updated = repository.update_tag(connection, tag_id, normalized_name, normalized_color)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "tags.html",
            {
                "title": "ipocket - Tags",
                "tags": list(repository.list_tags(connection)),
                "errors": ["Tag name already exists."],
                "form_state": {"name": "", "color": DEFAULT_TAG_COLOR},
            },
            status_code=409,
            active_nav="tags",
        )

    if updated is None:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/tags", status_code=303)


@router.post("/ui/tags/{tag_id}/delete", response_class=HTMLResponse)
async def ui_delete_tag(
    tag_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    deleted = repository.delete_tag(connection, tag_id)
    if not deleted:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/tags", status_code=303)


@router.get("/ui/ranges", response_class=HTMLResponse)
def ui_list_ranges(request: Request, connection=Depends(get_connection)) -> HTMLResponse:
    ranges = list(repository.list_ip_ranges(connection))
    utilization = repository.get_ip_range_utilization(connection)
    return _render_template(
        request,
        "ranges.html",
        {
            "title": "ipocket - IP Ranges",
            "ranges": ranges,
            "utilization": utilization,
            "errors": [],
            "form_state": {"name": "", "cidr": "", "notes": ""},
        },
        active_nav="ranges",
    )


@router.post("/ui/ranges", response_class=HTMLResponse)
async def ui_create_range(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append("CIDR must be a valid IPv4 network (example: 192.168.10.0/24).")

    if errors:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "ranges": ranges,
                "utilization": utilization,
                "errors": errors,
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        repository.create_ip_range(connection, name=name, cidr=normalized_cidr or cidr, notes=notes)
    except sqlite3.IntegrityError:
        ranges = list(repository.list_ip_ranges(connection))
        utilization = repository.get_ip_range_utilization(connection)
        return _render_template(
            request,
            "ranges.html",
            {
                "title": "ipocket - IP Ranges",
                "ranges": ranges,
                "utilization": utilization,
                "errors": ["CIDR already exists."],
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
            },
            status_code=409,
            active_nav="ranges",
        )

    return RedirectResponse(url="/ui/ranges", status_code=303)


@router.get("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
def ui_edit_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    return _render_template(
        request,
        "range_edit.html",
        {
            "title": "ipocket - Edit IP Range",
            "ip_range": ip_range,
            "errors": [],
            "form_state": {"name": ip_range.name, "cidr": ip_range.cidr, "notes": ip_range.notes or ""},
        },
        active_nav="ranges",
    )


@router.post("/ui/ranges/{range_id}/edit", response_class=HTMLResponse)
async def ui_update_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    cidr = (form_data.get("cidr") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    normalized_cidr = None
    if not name:
        errors.append("Range name is required.")
    if not cidr:
        errors.append("CIDR is required.")
    if cidr:
        try:
            normalized_cidr = normalize_cidr(cidr)
        except ValueError:
            errors.append("CIDR must be a valid IPv4 network (example: 192.168.10.0/24).")

    if errors:
        return _render_template(
            request,
            "range_edit.html",
            {
                "title": "ipocket - Edit IP Range",
                "ip_range": ip_range,
                "errors": errors,
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        updated_range = repository.update_ip_range(
            connection,
            range_id,
            name=name,
            cidr=normalized_cidr or cidr,
            notes=notes,
        )
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "range_edit.html",
            {
                "title": "ipocket - Edit IP Range",
                "ip_range": ip_range,
                "errors": ["CIDR already exists."],
                "form_state": {"name": name, "cidr": cidr, "notes": notes or ""},
            },
            status_code=409,
            active_nav="ranges",
        )

    if updated_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    return RedirectResponse(url="/ui/ranges", status_code=303)


@router.get("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
def ui_delete_range_confirm(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return _render_template(
        request,
        "range_delete_confirm.html",
        {
            "title": "ipocket - Confirm Range Delete",
            "ip_range": ip_range,
            "errors": [],
            "confirm_value": "",
        },
        active_nav="ranges",
    )


@router.post("/ui/ranges/{range_id}/delete", response_class=HTMLResponse)
async def ui_delete_range(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    ip_range = repository.get_ip_range_by_id(connection, range_id)
    if ip_range is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    if confirm_name != ip_range.name:
        return _render_template(
            request,
            "range_delete_confirm.html",
            {
                "title": "ipocket - Confirm Range Delete",
                "ip_range": ip_range,
                "errors": ["برای حذف کامل، نام رنج را دقیقاً وارد کنید."],
                "confirm_value": confirm_name,
            },
            status_code=400,
            active_nav="ranges",
        )

    deleted = repository.delete_ip_range(connection, range_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="IP range not found.")
    return RedirectResponse(url="/ui/ranges", status_code=303)


@router.get("/ui/ranges/{range_id}/addresses", response_class=HTMLResponse)
def ui_range_addresses(
    request: Request,
    range_id: int,
    connection=Depends(get_connection),
) -> HTMLResponse:
    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    addresses = breakdown["addresses"]
    display_limit = 512

    return _render_template(
        request,
        "range_addresses.html",
        {
            "title": "ipocket - Range Addresses",
            "ip_range": breakdown["ip_range"],
            "addresses": addresses,
            "used_total": breakdown["used"],
            "free_total": breakdown["free"],
            "total_usable": breakdown["total_usable"],
            "display_limit": display_limit,
            "address_display": addresses[:display_limit],
            "address_overflow": len(addresses) > display_limit,
            "projects": list(repository.list_projects(connection)),
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
        },
        active_nav="ranges",
    )


@router.post("/ui/ranges/{range_id}/addresses/add", response_class=HTMLResponse)
async def ui_range_quick_add_address(
    range_id: int,
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    projects = list(repository.list_projects(connection))

    errors: list[str] = []
    if not ip_address:
        errors.append("IP address is required.")
    else:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(exc.detail)

    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")

    if project_id is not None and not any(project.id == project_id for project in projects):
        errors.append("Selected project does not exist.")

    breakdown = repository.get_ip_range_address_breakdown(connection, range_id)
    if breakdown is None:
        raise HTTPException(status_code=404, detail="IP range not found.")

    address_lookup = {
        entry["ip_address"]: entry for entry in breakdown["addresses"]
    }
    if ip_address and ip_address not in address_lookup:
        errors.append("IP address is not part of this range.")
    elif ip_address and address_lookup[ip_address]["status"] != "free":
        errors.append("IP address is already assigned.")

    if errors:
        addresses = breakdown["addresses"]
        display_limit = 512
        return _render_template(
            request,
            "range_addresses.html",
            {
                "title": "ipocket - Range Addresses",
                "ip_range": breakdown["ip_range"],
                "addresses": addresses,
                "used_total": breakdown["used"],
                "free_total": breakdown["free"],
                "total_usable": breakdown["total_usable"],
                "display_limit": display_limit,
                "address_display": addresses[:display_limit],
                "address_overflow": len(addresses) > display_limit,
                "projects": projects,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
            },
            status_code=400,
            active_nav="ranges",
        )

    try:
        repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=normalized_asset_type,
            project_id=project_id,
            notes=None,
            tags=[],
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError:
        errors.append("IP address already exists.")

    if errors:
        addresses = breakdown["addresses"]
        display_limit = 512
        return _render_template(
            request,
            "range_addresses.html",
            {
                "title": "ipocket - Range Addresses",
                "ip_range": breakdown["ip_range"],
                "addresses": addresses,
                "used_total": breakdown["used"],
                "free_total": breakdown["free"],
                "total_usable": breakdown["total_usable"],
                "display_limit": display_limit,
                "address_display": addresses[:display_limit],
                "address_overflow": len(addresses) > display_limit,
                "projects": projects,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
            },
            status_code=409,
            active_nav="ranges",
        )

    ip_anchor = (ip_address or "").replace(".", "-").replace(":", "-")
    return RedirectResponse(
        url=f"/ui/ranges/{range_id}/addresses#ip-{ip_anchor}",
        status_code=303,
    )


@router.get("/ui/vendors", response_class=HTMLResponse)
def ui_list_vendors(request: Request, connection=Depends(get_connection)) -> HTMLResponse:
    vendors = list(repository.list_vendors(connection))
    return _render_template(
        request,
        "vendors.html",
        {
            "title": "ipocket - Vendors",
            "vendors": vendors,
            "errors": [],
            "form_state": {"name": ""},
        },
        active_nav="vendors",
    )


@router.post("/ui/vendors", response_class=HTMLResponse)
async def ui_create_vendor(request: Request, connection=Depends(get_connection), _user=Depends(require_ui_editor)) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    if not name:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name is required."],
                "form_state": {"name": name},
            },
            status_code=400,
            active_nav="vendors",
        )
    try:
        repository.create_vendor(connection, name=name)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name already exists."],
                "form_state": {"name": name},
            },
            status_code=409,
            active_nav="vendors",
        )
    return _redirect_with_flash(
        request,
        "/ui/vendors",
        "Vendor created.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/vendors/{vendor_id}/edit", response_class=HTMLResponse)
async def ui_edit_vendor(vendor_id: int, request: Request, connection=Depends(get_connection), _user=Depends(require_ui_editor)) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    if not name:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name is required."],
                "form_state": {"name": ""},
            },
            status_code=400,
            active_nav="vendors",
        )
    try:
        updated = repository.update_vendor(connection, vendor_id, name)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "vendors.html",
            {
                "title": "ipocket - Vendors",
                "vendors": list(repository.list_vendors(connection)),
                "errors": ["Vendor name already exists."],
                "form_state": {"name": ""},
            },
            status_code=409,
            active_nav="vendors",
        )
    if updated is None:
        return Response(status_code=404)
    return RedirectResponse(url="/ui/vendors", status_code=303)







@router.get("/ui/hosts", response_class=HTMLResponse)
def ui_list_hosts(
    request: Request,
    q: Optional[str] = None,
    connection=Depends(get_connection),
) -> HTMLResponse:
    hosts = repository.list_hosts_with_ip_counts(connection)
    q_value = (q or "").strip()
    if q_value:
        q_lower = q_value.lower()
        hosts = [
            host
            for host in hosts
            if q_lower in (host["name"] or "").lower()
            or q_lower in (host["notes"] or "").lower()
            or q_lower in (host["vendor"] or "").lower()
            or q_lower in (host["project_name"] or "").lower()
            or q_lower in (host["os_ips"] or "").lower()
            or q_lower in (host["bmc_ips"] or "").lower()
        ]
    return _render_template(
        request,
        "hosts.html",
        {
            "title": "ipocket - Hosts",
            "hosts": hosts,
            "errors": [],
            "vendors": list(repository.list_vendors(connection)),
            "projects": list(repository.list_projects(connection)),
            "form_state": {"name": "", "notes": "", "vendor_id": "", "os_ips": "", "bmc_ips": ""},
            "filters": {"q": q_value},
            "show_search": bool(q_value),
            "show_add_host": False,
        },
        active_nav="hosts",
    )


@router.post("/ui/hosts", response_class=HTMLResponse)
async def ui_create_host(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))
    vendor_id = _parse_optional_int(form_data.get("vendor_id"))
    os_ips_raw = form_data.get("os_ips")
    bmc_ips_raw = form_data.get("bmc_ips")
    os_ips = _parse_inline_ip_list(os_ips_raw)
    bmc_ips = _parse_inline_ip_list(bmc_ips_raw)

    errors = []
    if not name:
        errors.append("Host name is required.")
    inline_errors, inline_assets_to_create, inline_assets_to_update = _collect_inline_ip_errors(connection, None, os_ips, bmc_ips)
    errors.extend(inline_errors)

    if errors:
        hosts = repository.list_hosts_with_ip_counts(connection)
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": errors,
                "hosts": hosts,
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {
                    "name": name,
                    "notes": notes or "",
                    "vendor_id": str(vendor_id or ""),
                    "os_ips": os_ips_raw or "",
                    "bmc_ips": bmc_ips_raw or "",
                },
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": True,
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        vendor = repository.get_vendor_by_id(connection, vendor_id) if vendor_id is not None else None
        if vendor_id is not None and vendor is None:
            raise sqlite3.IntegrityError("Selected vendor does not exist.")
        host = repository.create_host(connection, name=name, notes=notes, vendor=vendor.name if vendor else None)
        # Create new IP assets
        for ip_address, asset_type in inline_assets_to_create:
            repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host.id,
                notes=None,
                tags=[],
                auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            )
        # Link existing IP assets to the host
        for ip_address, asset_type in inline_assets_to_update:
            repository.update_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host.id,
            )
    except sqlite3.IntegrityError:
        hosts = repository.list_hosts_with_ip_counts(connection)
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name already exists."],
                "hosts": hosts,
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {
                    "name": name,
                    "notes": notes or "",
                    "vendor_id": str(vendor_id or ""),
                    "os_ips": os_ips_raw or "",
                    "bmc_ips": bmc_ips_raw or "",
                },
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": True,
            },
            status_code=409,
            active_nav="hosts",
        )

    return _redirect_with_flash(
        request,
        "/ui/hosts",
        "Host created.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/hosts/{host_id}/edit", response_class=HTMLResponse)
async def ui_edit_host(
    host_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    notes = _parse_optional_str(form_data.get("notes"))
    vendor_id = _parse_optional_int(form_data.get("vendor_id"))
    os_ips_raw = form_data.get("os_ips")
    bmc_ips_raw = form_data.get("bmc_ips")
    project_raw = form_data.get("project_id")
    project_id = _parse_optional_int(project_raw)
    os_ips = _parse_inline_ip_list(os_ips_raw)
    bmc_ips = _parse_inline_ip_list(bmc_ips_raw)

    if not name:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name is required."],
                "toast_messages": [{"type": "error", "message": "Host name is required."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=400,
            active_nav="hosts",
        )

    vendor = repository.get_vendor_by_id(connection, vendor_id) if vendor_id is not None else None
    if vendor_id is not None and vendor is None:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Selected vendor does not exist."],
                "toast_messages": [{"type": "error", "message": "Selected vendor does not exist."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=422,
            active_nav="hosts",
        )

    inline_errors, inline_assets_to_create, inline_assets_to_update = _collect_inline_ip_errors(connection, host_id, os_ips, bmc_ips)
    if inline_errors:
        toast_messages = [{"type": "error", "message": error} for error in inline_errors]
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": inline_errors,
                "toast_messages": toast_messages,
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": "", "os_ips": "", "bmc_ips": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        updated = repository.update_host(
            connection,
            host_id=host_id,
            name=name,
            notes=notes,
            vendor=vendor.name if vendor else None,
        )
        set_project_id = project_raw is not None
        if set_project_id:
            projects = repository.list_projects(connection)
            if project_id is not None and all(project.id != project_id for project in projects):
                return _render_template(
                    request,
                    "hosts.html",
                    {
                        "title": "ipocket - Hosts",
                        "errors": ["Selected project does not exist."],
                        "toast_messages": [{"type": "error", "message": "Selected project does not exist."}],
                        "hosts": repository.list_hosts_with_ip_counts(connection),
                        "vendors": list(repository.list_vendors(connection)),
                        "projects": list(projects),
                        "form_state": {"name": "", "notes": "", "vendor_id": ""},
                        "filters": {"q": ""},
                        "show_search": False,
                        "show_add_host": False,
                    },
                    status_code=422,
                    active_nav="hosts",
                )
            linked = repository.get_host_linked_assets_grouped(connection, host_id)
            asset_ids = [asset.id for group in linked.values() for asset in group]
            if asset_ids:
                should_update = any(asset.project_id != project_id for group in linked.values() for asset in group)
                if should_update:
                    repository.bulk_update_ip_assets(
                        connection,
                        asset_ids,
                        project_id=project_id,
                        set_project_id=True,
                    )
        # Create new IP assets
        for ip_address, asset_type in inline_assets_to_create:
            repository.create_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host_id,
                notes=None,
                tags=[],
                auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            )
        # Link existing IP assets to the host
        for ip_address, asset_type in inline_assets_to_update:
            repository.update_ip_asset(
                connection,
                ip_address=ip_address,
                asset_type=asset_type,
                host_id=host_id,
            )
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name already exists."],
                "toast_messages": [{"type": "error", "message": "Host name already exists."}],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "projects": list(repository.list_projects(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
                "filters": {"q": ""},
                "show_search": False,
                "show_add_host": False,
            },
            status_code=409,
            active_nav="hosts",
        )

    if updated is None:
        return Response(status_code=404)

    return _redirect_with_flash(
        request,
        "/ui/hosts",
        "Host updated.",
        message_type="success",
        status_code=303,
    )


@router.get("/ui/hosts/{host_id}", response_class=HTMLResponse)
def ui_host_detail(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
) -> HTMLResponse:
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    grouped = repository.get_host_linked_assets_grouped(connection, host_id)
    return _render_template(
        request,
        "host_detail.html",
        {
            "title": "ipocket - Host Detail",
            "host": host,
            "os_assets": grouped["os"],
            "bmc_assets": grouped["bmc"],
            "other_assets": grouped["other"],
        },
        active_nav="hosts",
    )



@router.get("/ui/hosts/{host_id}/delete", response_class=HTMLResponse)
def ui_delete_host_confirm(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    linked = repository.get_host_linked_assets_grouped(connection, host_id)
    linked_count = len(linked["os"]) + len(linked["bmc"]) + len(linked["other"])
    return _render_template(
        request,
        "host_delete_confirm.html",
        {
            "title": "ipocket - Confirm Host Delete",
            "host": host,
            "linked_count": linked_count,
            "errors": [],
            "confirm_value": "",
        },
        active_nav="hosts",
    )


@router.post("/ui/hosts/{host_id}/delete", response_class=HTMLResponse)
async def ui_delete_host(
    request: Request,
    host_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    host = repository.get_host_by_id(connection, host_id)
    if host is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    linked = repository.get_host_linked_assets_grouped(connection, host_id)
    linked_count = len(linked["os"]) + len(linked["bmc"]) + len(linked["other"])

    form_data = await _parse_form_data(request)
    confirm_name = (form_data.get("confirm_name") or "").strip()
    if confirm_name != host.name:
        return _render_template(
            request,
            "host_delete_confirm.html",
            {
                "title": "ipocket - Confirm Host Delete",
                "host": host,
                "linked_count": linked_count,
                "errors": ["برای حذف کامل، نام Host را دقیقاً وارد کنید."],
                "confirm_value": confirm_name,
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        deleted = repository.delete_host(connection, host_id)
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "host_delete_confirm.html",
            {
                "title": "ipocket - Confirm Host Delete",
                "host": host,
                "linked_count": linked_count,
                "errors": ["این Host هنوز IP لینک‌شده دارد و قابل حذف نیست."],
                "confirm_value": confirm_name,
            },
            status_code=409,
            active_nav="hosts",
        )

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return RedirectResponse(url="/ui/hosts", status_code=303)

@router.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    tag: Optional[list[str]] = Query(default=None),
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    archived_only: bool = Query(default=False, alias="archived-only"),
    bulk_error: Optional[str] = Query(default=None, alias="bulk-error"),
    bulk_success: Optional[str] = Query(default=None, alias="bulk-success"),
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    parsed_project_id = _parse_optional_int_query(project_id)
    try:
        asset_type_enum = _normalize_asset_type(asset_type)
    except ValueError:
        asset_type_enum = None
    q_value = (q or "").strip()
    query_text = q_value or None
    raw_tag_values = tag or []
    try:
        tag_values = normalize_tag_names(raw_tag_values) if raw_tag_values else []
    except ValueError:
        tag_values = []
    total_count = repository.count_active_ip_assets(
        connection,
        project_id=parsed_project_id,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        archived_only=archived_only,
    )
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    assets = repository.list_active_ip_assets_paginated(
        connection,
        project_id=parsed_project_id,
        asset_type=asset_type_enum,
        unassigned_only=unassigned_only,
        query_text=query_text,
        tag_names=tag_values,
        limit=per_page_value,
        offset=offset,
        archived_only=archived_only,
    )

    projects = list(repository.list_projects(connection))
    tags = list(repository.list_tags(connection))
    project_lookup = {project.id: {"name": project.name, "color": project.color} for project in projects}
    hosts = list(repository.list_hosts(connection))
    host_lookup = {host.id: host.name for host in hosts}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id for asset in assets])
    host_pair_lookup = repository.list_host_pair_ips_for_hosts(
        connection,
        [asset.host_id for asset in assets if asset.host_id],
    )
    view_models = _build_asset_view_models(
        assets,
        project_lookup,
        host_lookup,
        tag_lookup,
        host_pair_lookup,
    )

    is_htmx = request.headers.get("HX-Request") is not None
    template_name = "partials/ip_assets_table.html" if is_htmx else "ip_assets_list.html"
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    pagination_params: dict[str, object] = {"per-page": per_page_value}
    if q_value:
        pagination_params["q"] = q_value
    if parsed_project_id is not None:
        pagination_params["project_id"] = parsed_project_id
    if tag_values:
        pagination_params["tag"] = tag_values
    if asset_type_enum:
        pagination_params["type"] = asset_type_enum.value
    if unassigned_only:
        pagination_params["unassigned-only"] = "true"
    if archived_only:
        pagination_params["archived-only"] = "true"
    base_query = urlencode(pagination_params, doseq=True)
    return_to = request.url.path
    if request.url.query:
        return_to = f"{return_to}?{request.url.query}"
    toast_messages: list[dict[str, str]] = []
    if bulk_error:
        toast_messages.append({"type": "error", "message": bulk_error})
    if bulk_success:
        toast_messages.append({"type": "success", "message": bulk_success})
    context = {
        "title": "ipocket - IP Assets",
        "assets": view_models,
        "projects": projects,
        "tags": tags,
        "hosts": hosts,
        "types": [asset.value for asset in IPAssetType],
        "return_to": return_to,
        "toast_messages": toast_messages,
        "pagination": {
            "page": page_value,
            "per_page": per_page_value,
            "total": total_count,
            "total_pages": total_pages,
            "has_prev": page_value > 1,
            "has_next": page_value < total_pages,
            "start_index": start_index,
            "end_index": end_index,
            "base_query": base_query,
        },
    }
    if not is_htmx:
        context.update(
            {
                "filters": {
                    "q": q or "",
                    "project_id": parsed_project_id,
                    "tag": tag_values,
                    "type": asset_type_enum.value if asset_type_enum else "",
                    "unassigned_only": unassigned_only,
                    "archived_only": archived_only,
                    "page": page_value,
                    "per_page": per_page_value,
                },
            }
        )

    return _render_template(
        request,
        template_name,
        context,
        active_nav="ip-assets",
    )


@router.post("/ui/ip-assets/bulk-edit", response_class=HTMLResponse)
async def ui_bulk_edit_ip_assets(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    form = await request.form()
    asset_ids_raw = form.getlist("asset_ids")
    return_to = form.get("return_to") or "/ui/ip-assets"
    errors: list[str] = []
    asset_ids: list[int] = []
    for asset_id in asset_ids_raw:
        try:
            asset_ids.append(int(asset_id))
        except (TypeError, ValueError):
            errors.append("Select valid IP assets.")
            break
    if not asset_ids:
        errors.append("Select at least one IP asset.")

    asset_type_raw = (form.get("type") or "").strip()
    asset_type_enum: Optional[IPAssetType] = None
    if asset_type_raw:
        try:
            asset_type_enum = _normalize_asset_type(asset_type_raw)
        except ValueError:
            errors.append("Select a valid type.")

    project_selection = (form.get("project_id") or "").strip()
    set_project_id = False
    project_id_value: Optional[int] = None
    if project_selection:
        set_project_id = True
        if project_selection == "unassigned":
            project_id_value = None
        else:
            project_id_value = _parse_optional_int(project_selection)
            if project_id_value is None:
                errors.append("Select a valid project.")
            elif repository.get_project_by_id(connection, project_id_value) is None:
                errors.append("Selected project does not exist.")

    tags_raw = (form.get("tags") or "").strip()
    tags_to_add: list[str] = []
    if tags_raw:
        try:
            tags_to_add = normalize_tag_names(split_tag_string(tags_raw))
        except ValueError as exc:
            errors.append(str(exc))

    if not asset_type_enum and not set_project_id and not tags_to_add:
        errors.append("Choose at least one bulk update action.")

    if errors:
        message = errors[0]
        return RedirectResponse(
            url=_append_query_param(return_to, "bulk-error", message),
            status_code=303,
        )

    updated_assets = repository.bulk_update_ip_assets(
        connection,
        asset_ids,
        asset_type=asset_type_enum,
        project_id=project_id_value,
        set_project_id=set_project_id,
        tags_to_add=tags_to_add,
        current_user=user,
    )
    success_message = f"Updated {len(updated_assets)} IP assets."
    return RedirectResponse(
        url=_append_query_param(return_to, "bulk-success", success_message),
        status_code=303,
    )


@router.get("/ui/audit-log", response_class=HTMLResponse)
def ui_audit_log(
    request: Request,
    page: Optional[str] = None,
    per_page: Optional[str] = Query(default=None, alias="per-page"),
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    per_page_value = _parse_positive_int_query(per_page, 20)
    allowed_page_sizes = {10, 20, 50, 100}
    if per_page_value not in allowed_page_sizes:
        per_page_value = 20
    page_value = _parse_positive_int_query(page, 1)
    total_count = repository.count_audit_logs(connection)
    total_pages = max(1, math.ceil(total_count / per_page_value)) if total_count else 1
    page_value = max(1, min(page_value, total_pages))
    offset = (page_value - 1) * per_page_value if total_count else 0
    audit_logs = repository.list_audit_logs_paginated(
        connection,
        limit=per_page_value,
        offset=offset,
    )
    audit_log_rows = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": log.changes or "",
            "target_label": log.target_label,
        }
        for log in audit_logs
    ]
    start_index = (page_value - 1) * per_page_value + 1 if total_count else 0
    end_index = min(page_value * per_page_value, total_count) if total_count else 0
    base_query = urlencode({"per-page": per_page_value})
    return _render_template(
        request,
        "audit_log_list.html",
        {
            "title": "ipocket - Audit Log",
            "audit_logs": audit_log_rows,
            "pagination": {
                "page": page_value,
                "per_page": per_page_value,
                "total": total_count,
                "total_pages": total_pages,
                "has_prev": page_value > 1,
                "has_next": page_value < total_pages,
                "start_index": start_index,
                "end_index": end_index,
                "base_query": base_query,
            },
        },
        active_nav="audit-log",
    )


@router.get("/ui/ip-assets/needs-assignment", response_class=HTMLResponse)
def ui_needs_assignment(
    request: Request,
    filter: Optional[str] = None,
    connection=Depends(get_connection),
):
    assignment_filter = _normalize_assignment_filter(filter)
    assets = list(
        repository.list_ip_assets_needing_assignment(connection, assignment_filter)
    )
    projects = list(repository.list_projects(connection))
    project_lookup = {project.id: {"name": project.name, "color": project.color} for project in projects}
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id for asset in assets])
    view_models = _build_asset_view_models(assets, project_lookup, host_lookup, tag_lookup)
    form_state = {
        "ip_address": view_models[0]["ip_address"] if view_models else "",
        "project_id": None,
    }
    return _render_template(
        request,
        "needs_assignment.html",
        {
            "title": "ipocket - Needs Assignment",
            "assets": view_models,
            "projects": projects,
            "selected_filter": assignment_filter,
            "errors": [],
            "form_state": form_state,
        },
        active_nav="needs-assignment",
    )


@router.post("/ui/ip-assets/needs-assignment/assign", response_class=HTMLResponse)
async def ui_needs_assignment_assign(
    request: Request,
    filter: Optional[str] = None,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    assignment_filter = _normalize_assignment_filter(filter)
    form_data = await _parse_form_data(request)
    ip_address = (form_data.get("ip_address") or "").strip()
    project_id = _parse_optional_int(form_data.get("project_id"))

    errors = []
    if not ip_address:
        errors.append("Select an IP address.")
    if project_id is None:
        errors.append("Assign Project.")

    asset = None
    if ip_address:
        asset = repository.get_ip_asset_by_ip(connection, ip_address)
        if asset is None or asset.archived:
            errors.append("Selected IP address was not found.")

    if errors:
        assets = list(
            repository.list_ip_assets_needing_assignment(
                connection, assignment_filter
            )
        )
        projects = list(repository.list_projects(connection))
        project_lookup = {project.id: {"name": project.name, "color": project.color} for project in projects}
        host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
        tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id for asset in assets])
        view_models = _build_asset_view_models(assets, project_lookup, host_lookup, tag_lookup)
        return _render_template(
            request,
            "needs_assignment.html",
            {
                "title": "ipocket - Needs Assignment",
                "assets": view_models,
                "projects": projects,
                "selected_filter": assignment_filter,
                "errors": errors,
                "form_state": {
                    "ip_address": ip_address,
                    "project_id": project_id,
                },
            },
            active_nav="needs-assignment",
        )

    repository.update_ip_asset(
        connection,
        ip_address=ip_address,
        project_id=project_id,
        current_user=user,
    )
    return RedirectResponse(
        url=f"/ui/ip-assets/needs-assignment?filter={assignment_filter}",
        status_code=303,
    )


@router.get("/ui/ip-assets/new", response_class=HTMLResponse)
def ui_add_ip_form(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    return _render_template(
        request,
        "ip_asset_form.html",
        {
            "title": "ipocket - Add IP",
            "asset": {
                "id": None,
                "ip_address": "",
                "type": IPAssetType.VM.value,
                "project_id": "",
                "host_id": "",
                "notes": "",
                "tags": "",
            },
            "projects": projects,
            "hosts": hosts,
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
            "mode": "create",
            "action_url": "/ui/ip-assets/new",
            "submit_label": "Create",
        },
        active_nav="ip-assets",
    )


@router.post("/ui/ip-assets/new", response_class=HTMLResponse)
async def ui_add_ip_submit(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    form_data = await _parse_form_data(request)
    ip_address = form_data.get("ip_address")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.get("tags") or ""

    errors = []
    if not ip_address:
        errors.append("IP address is required.")
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if host_id is not None and repository.get_host_by_id(connection, host_id) is None:
        errors.append("Selected host does not exist.")

    if ip_address:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(exc.detail)
    try:
        tags = normalize_tag_names(split_tag_string(tags_raw)) if tags_raw else []
    except ValueError as exc:
        tags = []
        errors.append(str(exc))

    if errors:
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Add IP",
                "asset": {
                    "id": None,
                    "ip_address": ip_address or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags_raw,
                },
                "projects": projects,
                "hosts": hosts,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "create",
                "action_url": "/ui/ip-assets/new",
                "submit_label": "Create",
            },
            status_code=400,
            active_nav="ip-assets",
        )

    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=ip_address,
            asset_type=normalized_asset_type,
            project_id=project_id,
            host_id=host_id,
            notes=notes,
            tags=tags,
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
            current_user=user,
        )
    except sqlite3.IntegrityError:
        errors.append("IP address already exists.")
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Add IP",
                "asset": {
                    "id": None,
                    "ip_address": ip_address or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags_raw,
                },
                "projects": projects,
                "hosts": hosts,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "create",
                "action_url": "/ui/ip-assets/new",
                "submit_label": "Create",
            },
            status_code=409,
            active_nav="ip-assets",
        )

    return _redirect_with_flash(
        request,
        f"/ui/ip-assets/{asset.id}",
        "IP asset created.",
        message_type="success",
        status_code=303,
    )


@router.get("/ui/ip-assets/{asset_id}", response_class=HTMLResponse)
def ui_ip_asset_detail(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(get_current_ui_user),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    project_lookup = {
        project.id: {"name": project.name, "color": project.color}
        for project in repository.list_projects(connection)
    }
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    tag_lookup = repository.list_tag_details_for_ip_assets(connection, [asset.id])
    view_model = _build_asset_view_models([asset], project_lookup, host_lookup, tag_lookup)[0]
    audit_logs = repository.get_audit_logs_for_ip(connection, asset.id)
    audit_log_rows = [
        {
            "created_at": log.created_at,
            "user": log.username or "System",
            "action": log.action,
            "changes": log.changes or "",
        }
        for log in audit_logs
    ]
    return _render_template(
        request,
        "ip_asset_detail.html",
        {"title": "ipocket - IP Detail", "asset": view_model, "audit_logs": audit_log_rows},
        active_nav="ip-assets",
    )


@router.get("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
def ui_edit_ip_form(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    projects = list(repository.list_projects(connection))
    hosts = list(repository.list_hosts(connection))
    tag_lookup = repository.list_tags_for_ip_assets(connection, [asset.id])
    tags_value = ", ".join(tag_lookup.get(asset.id, []))
    return _render_template(
        request,
        "ip_asset_form.html",
        {
            "title": "ipocket - Edit IP",
            "asset": {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "type": asset.asset_type.value,
                "project_id": asset.project_id or "",
                "host_id": asset.host_id or "",
                "notes": asset.notes or "",
                "tags": tags_value,
            },
            "projects": projects,
            "hosts": hosts,
            "types": [asset.value for asset in IPAssetType],
            "errors": [],
            "mode": "edit",
            "action_url": f"/ui/ip-assets/{asset.id}/edit",
            "submit_label": "Save changes",
        },
        active_nav="ip-assets",
    )


@router.post("/ui/ip-assets/{asset_id}/auto-host", response_class=JSONResponse)
def ui_create_auto_host(
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
) -> JSONResponse:
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if asset.asset_type != IPAssetType.BMC:
        return JSONResponse({"error": "Auto-host creation is only available for BMC assets."}, status_code=400)
    if asset.host_id is not None:
        return JSONResponse({"error": "This IP is already assigned to a host."}, status_code=409)

    host_name = f"server_{asset.ip_address}"
    host = repository.get_host_by_name(connection, host_name)
    if host is None:
        host = repository.create_host(connection, name=host_name, notes=None, vendor=None)

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        host_id=host.id,
        current_user=user,
    )

    return JSONResponse({"host_id": host.id, "host_name": host.name})


@router.post("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
async def ui_edit_ip_submit(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form_data = await _parse_form_data(request)
    return_to = (form_data.get("return_to") or "").strip()
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))
    tags_raw = form_data.get("tags") or ""

    errors = []
    normalized_asset_type = None
    try:
        normalized_asset_type = _normalize_asset_type(asset_type)
    except ValueError:
        errors.append("Asset type is required.")
    if normalized_asset_type is None and not errors:
        errors.append("Asset type is required.")
    if host_id is not None and repository.get_host_by_id(connection, host_id) is None:
        errors.append("Selected host does not exist.")
    try:
        tags = normalize_tag_names(split_tag_string(tags_raw)) if tags_raw else []
    except ValueError as exc:
        tags = []
        errors.append(str(exc))

    if errors:
        projects = list(repository.list_projects(connection))
        hosts = list(repository.list_hosts(connection))
        return _render_template(
            request,
            "ip_asset_form.html",
            {
                "title": "ipocket - Edit IP",
                "asset": {
                    "id": asset.id,
                    "ip_address": asset.ip_address,
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
                    "tags": tags_raw,
                },
                "projects": projects,
                "hosts": hosts,
                "types": [asset.value for asset in IPAssetType],
                "errors": errors,
                "mode": "edit",
                "action_url": f"/ui/ip-assets/{asset.id}/edit",
                "submit_label": "Save changes",
            },
            status_code=400,
            active_nav="ip-assets",
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        asset_type=normalized_asset_type,
        project_id=project_id,
        host_id=host_id,
        notes=notes,
        tags=tags,
        current_user=user,
        notes_provided=True,
    )
    if return_to.startswith("/"):
        return RedirectResponse(url=return_to, status_code=303)
    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)




@router.get("/ui/ip-assets/{asset_id}/delete", response_class=HTMLResponse)
def ui_delete_ip_asset_confirm(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _render_template(
        request,
        "ip_asset_delete_confirm.html",
        {
            "title": "ipocket - Confirm IP Delete",
            "asset": asset,
            "errors": [],
            "confirm_value": "",
        },
        active_nav="ip-assets",
    )


@router.post("/ui/ip-assets/{asset_id}/delete", response_class=HTMLResponse)
async def ui_delete_ip_asset(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form_data = await _parse_form_data(request)
    confirm_ip = (form_data.get("confirm_ip") or "").strip()
    if confirm_ip != asset.ip_address:
        return _render_template(
            request,
            "ip_asset_delete_confirm.html",
            {
                "title": "ipocket - Confirm IP Delete",
                "asset": asset,
                "errors": ["برای حذف کامل، آدرس IP را دقیقاً وارد کنید."],
                "confirm_value": confirm_ip,
            },
            status_code=400,
            active_nav="ip-assets",
        )

    repository.delete_ip_asset(connection, asset.ip_address, current_user=user)
    return RedirectResponse(url="/ui/ip-assets", status_code=303)


@router.post("/ui/ip-assets/{asset_id}/archive")
def ui_archive_ip_asset(
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    repository.archive_ip_asset(connection, asset.ip_address)
    return RedirectResponse(url="/ui/ip-assets", status_code=303)
