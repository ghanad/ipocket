from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Request
from fastapi.responses import HTMLResponse

from app import build_info
from app.environment import use_local_assets

from .session import FLASH_COOKIE


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
    from app.routes.ui import utils as ui_utils

    is_authenticated = ui_module._is_authenticated_request(request)
    is_superuser = ui_module._is_superuser_request(request)
    flash_messages = ui_utils._load_flash_messages(request)
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
        "is_superuser": is_superuser,
        "build_info": build_info.get_display_build_info(),
        "toast_messages": toast_messages,
        **context,
    }
    if templates is None:
        return _render_fallback_template(
            template_name, payload, status_code=status_code
        )
    response = templates.TemplateResponse(
        request, template_name, payload, status_code=status_code
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
        name = (
            getattr(host, "name", None)
            if not isinstance(host, dict)
            else host.get("name")
        )
        if name:
            lines.append(str(name))
    for vendor in payload.get("vendors") or []:
        name = (
            getattr(vendor, "name", None)
            if not isinstance(vendor, dict)
            else vendor.get("name")
        )
        if name:
            lines.append(str(name))
    if template_name == "management.html":
        summary = payload.get("summary") or {}
        for key in (
            "active_ip_total",
            "archived_ip_total",
            "host_total",
            "vendor_total",
            "project_total",
        ):
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
        lines.append(f"ipocket {version} ({commit}) • built {build_time}")
    return HTMLResponse(content="\n".join(lines), status_code=status_code)
