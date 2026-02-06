from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import zipfile
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app import auth, build_info, exports, repository
from app.dependencies import get_connection
from app.models import IPAsset, IPAssetType, UserRole
from app.utils import validate_ip_address

router = APIRouter()

SESSION_COOKIE = "ipocket_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret").encode("utf-8")


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
    payload = {
        "request": request,
        "show_nav": show_nav,
        "active_nav": active_nav,
        "build_info": build_info.get_display_build_info() if _is_authenticated_request(request) else None,
        **context,
    }
    if templates is None:
        return _render_fallback_template(
            template_name, payload, status_code=status_code
        )
    return templates.TemplateResponse(
        template_name, payload, status_code=status_code
    )


def _render_fallback_template(
    template_name: str, payload: dict, status_code: int = 200
) -> HTMLResponse:
    lines = [
        '<link rel="stylesheet" href="/static/app.css" />',
        str(payload.get("title", "ipocket")),
    ]
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


def _is_authenticated_request(request: Request) -> bool:
    signed_session = request.cookies.get(SESSION_COOKIE)
    return _verify_session_value(signed_session) is not None


def get_current_ui_user(
    request: Request, connection=Depends(get_connection)
):
    signed_session = request.cookies.get(SESSION_COOKIE)
    user_id = _verify_session_value(signed_session)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/ui/login"},
        )
    user = repository.get_user_by_id(connection, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/ui/login"},
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
    project_lookup: dict[int, str],
    host_lookup: dict[int, str],
) -> list[dict]:
    view_models = []
    for asset in assets:
        project_name = project_lookup.get(asset.project_id) if asset.project_id else ""
        project_unassigned = not project_name
        host_name = host_lookup.get(asset.host_id) if asset.host_id else ""
        view_models.append(
            {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "subnet": asset.subnet,
                "gateway": asset.gateway,
                "type": asset.asset_type.value,
                "project_name": project_name,
                "notes": asset.notes or "",
                "host_name": host_name,
                "unassigned": _is_unassigned(asset.project_id),
                "project_unassigned": project_unassigned,
            }
        )
    return view_models


async def _parse_form_data(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode())
    return {key: values[0] for key, values in parsed.items()}


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
        "subnet",
        "gateway",
        "type",
        "project_name",
        "host_name",
        "notes",
        "archived",
        "created_at",
        "updated_at",
    ]
    return _csv_response("ip-assets.csv", headers, export_rows)


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
    headers = ["name", "description"]
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
                "subnet",
                "gateway",
                "type",
                "project_name",
                "host_name",
                "notes",
                "archived",
                "created_at",
                "updated_at",
            ],
            ip_assets,
        ),
        "projects.csv": _build_csv_content(["name", "description"], projects),
        "hosts.csv": _build_csv_content(["name", "notes", "vendor_name"], hosts),
        "vendors.csv": _build_csv_content(["name"], vendors),
    }
    return _zip_response("bundle.zip", files)


@router.get("/ui/login", response_class=HTMLResponse)
def ui_login_form(request: Request) -> HTMLResponse:
    return _render_template(
        request,
        "login.html",
        {"title": "ipocket - Login", "error_message": ""},
        show_nav=False,
    )


@router.post("/ui/login", response_class=HTMLResponse)
async def ui_login_submit(
    request: Request, connection=Depends(get_connection)
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""

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
            },
            status_code=401,
            show_nav=False,
        )

    response = RedirectResponse(url="/ui/ip-assets", status_code=303)
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
            "form_state": {"name": "", "description": ""},
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

    errors = []
    if not name:
        errors.append("Project name is required.")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": "", "description": ""},
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
                "form_state": {"name": "", "description": ""},
            },
            status_code=409,
            active_nav="projects",
        )

    if updated is None:
        return Response(status_code=404)

    return RedirectResponse(url="/ui/projects", status_code=303)


@router.post("/ui/projects", response_class=HTMLResponse)
async def ui_create_project(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    description = _parse_optional_str(form_data.get("description"))

    errors = []
    if not name:
        errors.append("Project name is required.")

    if errors:
        projects = list(repository.list_projects(connection))
        return _render_template(
            request,
            "projects.html",
            {
                "title": "ipocket - Projects",
                "projects": projects,
                "errors": errors,
                "form_state": {"name": name, "description": description or ""},
            },
            status_code=400,
            active_nav="projects",
        )

    try:
        repository.create_project(connection, name=name, description=description)
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
                "form_state": {"name": name, "description": description or ""},
            },
            status_code=409,
            active_nav="projects",
        )

    return RedirectResponse(url="/ui/projects", status_code=303)


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
    return RedirectResponse(url="/ui/vendors", status_code=303)


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
    connection=Depends(get_connection),
) -> HTMLResponse:
    hosts = repository.list_hosts_with_ip_counts(connection)
    return _render_template(
        request,
        "hosts.html",
        {
            "title": "ipocket - Hosts",
            "hosts": hosts,
            "errors": [],
            "vendors": list(repository.list_vendors(connection)),
            "form_state": {"name": "", "notes": "", "vendor_id": ""},
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

    errors = []
    if not name:
        errors.append("Host name is required.")

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
                "form_state": {"name": name, "notes": notes or "", "vendor_id": str(vendor_id or "")},
            },
            status_code=400,
            active_nav="hosts",
        )

    try:
        vendor = repository.get_vendor_by_id(connection, vendor_id) if vendor_id is not None else None
        if vendor_id is not None and vendor is None:
            raise sqlite3.IntegrityError("Selected vendor does not exist.")
        repository.create_host(connection, name=name, notes=notes, vendor=vendor.name if vendor else None)
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
                "form_state": {"name": name, "notes": notes or "", "vendor_id": str(vendor_id or "")},
            },
            status_code=409,
            active_nav="hosts",
        )

    return RedirectResponse(url="/ui/hosts", status_code=303)


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

    if not name:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name is required."],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
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
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
            },
            status_code=422,
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
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "hosts.html",
            {
                "title": "ipocket - Hosts",
                "errors": ["Host name already exists."],
                "hosts": repository.list_hosts_with_ip_counts(connection),
                "vendors": list(repository.list_vendors(connection)),
                "form_state": {"name": "", "notes": "", "vendor_id": ""},
            },
            status_code=409,
            active_nav="hosts",
        )

    if updated is None:
        return Response(status_code=404)

    return RedirectResponse(url="/ui/hosts", status_code=303)


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
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    parsed_project_id = _parse_optional_int_query(project_id)
    try:
        asset_type_enum = _normalize_asset_type(asset_type)
    except ValueError:
        asset_type_enum = None
    assets = list(
        repository.list_active_ip_assets(
            connection,
            project_id=parsed_project_id,
            asset_type=asset_type_enum,
            unassigned_only=unassigned_only,
        )
    )
    if q:
        q_lower = q.lower()
        assets = [
            asset
            for asset in assets
            if q_lower in asset.ip_address.lower()
            or (asset.notes or "").lower().find(q_lower) >= 0
        ]

    projects = list(repository.list_projects(connection))
    project_lookup = {project.id: project.name for project in projects}
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    view_models = _build_asset_view_models(assets, project_lookup, host_lookup)

    return _render_template(
        request,
        "ip_assets_list.html",
        {
            "title": "ipocket - IP Assets",
            "assets": view_models,
            "projects": projects,
            "types": [asset.value for asset in IPAssetType],
            "filters": {
                "q": q or "",
                "project_id": parsed_project_id,
                "type": asset_type_enum.value if asset_type_enum else "",
                "unassigned_only": unassigned_only,
            },
        },
        active_nav="ip-assets",
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
    project_lookup = {project.id: project.name for project in projects}
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    view_models = _build_asset_view_models(assets, project_lookup, host_lookup)
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
    _user=Depends(require_ui_editor),
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
        project_lookup = {project.id: project.name for project in projects}
        host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
        view_models = _build_asset_view_models(assets, project_lookup, host_lookup)
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
                "subnet": "",
                "gateway": "",
                "type": IPAssetType.VM.value,
                "project_id": "",
                "host_id": "",
                "notes": "",
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
    _user=Depends(require_ui_editor),
):
    form_data = await _parse_form_data(request)
    ip_address = form_data.get("ip_address")
    subnet = (form_data.get("subnet") or "").strip()
    gateway = (form_data.get("gateway") or "").strip()
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))

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
                    "subnet": subnet or "",
                    "gateway": gateway or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
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
            subnet=subnet,
            gateway=gateway,
            asset_type=normalized_asset_type,
            project_id=project_id,
            host_id=host_id,
            notes=notes,
            auto_host_for_bmc=_is_auto_host_for_bmc_enabled(),
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
                    "subnet": subnet or "",
                    "gateway": gateway or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
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

    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)


@router.get("/ui/ip-assets/{asset_id}", response_class=HTMLResponse)
def ui_ip_asset_detail(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    project_lookup = {
        project.id: project.name for project in repository.list_projects(connection)
    }
    host_lookup = {host.id: host.name for host in repository.list_hosts(connection)}
    view_model = _build_asset_view_models([asset], project_lookup, host_lookup)[0]
    return _render_template(
        request,
        "ip_asset_detail.html",
        {"title": "ipocket - IP Detail", "asset": view_model},
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
    return _render_template(
        request,
        "ip_asset_form.html",
        {
            "title": "ipocket - Edit IP",
            "asset": {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "subnet": asset.subnet,
                "gateway": asset.gateway,
                "type": asset.asset_type.value,
                "project_id": asset.project_id or "",
                "host_id": asset.host_id or "",
                "notes": asset.notes or "",
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


@router.post("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
async def ui_edit_ip_submit(
    request: Request,
    asset_id: int,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    asset = repository.get_ip_asset_by_id(connection, asset_id)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form_data = await _parse_form_data(request)
    subnet = (form_data.get("subnet") or "").strip()
    gateway = (form_data.get("gateway") or "").strip()
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    host_id = _parse_optional_int(form_data.get("host_id"))
    notes = _parse_optional_str(form_data.get("notes"))

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
                    "subnet": subnet or "",
                    "gateway": gateway or "",
                    "type": asset_type or "",
                    "project_id": project_id or "",
                    "host_id": host_id or "",
                    "notes": notes or "",
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
        subnet=subnet,
        gateway=gateway,
        asset_type=normalized_asset_type,
        project_id=project_id,
        host_id=host_id,
        notes=notes,
    )
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
    _user=Depends(require_ui_editor),
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

    repository.delete_ip_asset(connection, asset.ip_address)
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
