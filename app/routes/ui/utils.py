from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import zipfile
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import build_info, repository
from app.dependencies import get_connection
from app.environment import use_local_assets
from app.models import IPAsset, IPAssetType, UserRole
from app.utils import normalize_hex_color, validate_ip_address

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
    from app.routes import ui as ui_module

    is_authenticated = ui_module._is_authenticated_request(request)
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
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}

async def _parse_multipart_form(request: Request) -> dict:
    form = await request.form()
    return dict(form)
