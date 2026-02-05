from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app import auth, build_info, repository
from app.dependencies import get_connection
from app.models import IPAsset, IPAssetType, UserRole
from app.utils import validate_ip_address

router = APIRouter()

SESSION_COOKIE = "ipocket_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret").encode("utf-8")


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
        if asset.get("project_unassigned") or asset.get("owner_unassigned"):
            lines.append("Unassigned")
    for project in payload.get("projects") or []:
        name = getattr(project, "name", None)
        if name:
            lines.append(str(name))
    for owner in payload.get("owners") or []:
        name = getattr(owner, "name", None)
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


def _is_unassigned(project_id: Optional[int], owner_id: Optional[int]) -> bool:
    return project_id is None or owner_id is None


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
    if value in {"owner", "project", "both"}:
        return value
    return "owner"


def _build_asset_view_models(
    assets: list[IPAsset],
    project_lookup: dict[int, str],
    owner_lookup: dict[int, str],
) -> list[dict]:
    view_models = []
    for asset in assets:
        project_name = project_lookup.get(asset.project_id) if asset.project_id else ""
        owner_name = owner_lookup.get(asset.owner_id) if asset.owner_id else ""
        project_unassigned = not project_name
        owner_unassigned = not owner_name
        view_models.append(
            {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "subnet": asset.subnet,
                "gateway": asset.gateway,
                "type": asset.asset_type.value,
                "project_name": project_name,
                "owner_name": owner_name,
                "notes": asset.notes or "",
                "unassigned": _is_unassigned(asset.project_id, asset.owner_id),
                "project_unassigned": project_unassigned,
                "owner_unassigned": owner_unassigned,
                "both_unassigned": project_unassigned and owner_unassigned,
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


@router.get("/ui/owners", response_class=HTMLResponse)
def ui_list_owners(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    owners = list(repository.list_owners(connection))
    return _render_template(
        request,
        "owners.html",
        {
            "title": "ipocket - Owners",
            "owners": owners,
            "errors": [],
            "form_state": {"name": "", "contact": ""},
        },
        active_nav="owners",
    )


@router.post("/ui/owners/{owner_id}/edit", response_class=HTMLResponse)
async def ui_update_owner(
    owner_id: int,
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    contact = _parse_optional_str(form_data.get("contact"))

    errors = []
    if not name:
        errors.append("Owner name is required.")

    if errors:
        owners = list(repository.list_owners(connection))
        return _render_template(
            request,
            "owners.html",
            {
                "title": "ipocket - Owners",
                "owners": owners,
                "errors": errors,
                "form_state": {"name": "", "contact": ""},
            },
            status_code=400,
            active_nav="owners",
        )

    try:
        updated = repository.update_owner(
            connection,
            owner_id=owner_id,
            name=name,
            contact=contact,
        )
    except sqlite3.IntegrityError:
        owners = list(repository.list_owners(connection))
        return _render_template(
            request,
            "owners.html",
            {
                "title": "ipocket - Owners",
                "owners": owners,
                "errors": ["Owner name already exists."],
                "form_state": {"name": "", "contact": ""},
            },
            status_code=409,
            active_nav="owners",
        )

    if updated is None:
        return Response(status_code=404)

    return RedirectResponse(url="/ui/owners", status_code=303)


@router.post("/ui/owners", response_class=HTMLResponse)
async def ui_create_owner(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    name = (form_data.get("name") or "").strip()
    contact = _parse_optional_str(form_data.get("contact"))

    errors = []
    if not name:
        errors.append("Owner name is required.")

    if errors:
        owners = list(repository.list_owners(connection))
        return _render_template(
            request,
            "owners.html",
            {
                "title": "ipocket - Owners",
                "owners": owners,
                "errors": errors,
                "form_state": {"name": name, "contact": contact or ""},
            },
            status_code=400,
            active_nav="owners",
        )

    try:
        repository.create_owner(connection, name=name, contact=contact)
    except sqlite3.IntegrityError:
        errors.append("Owner name already exists.")
        owners = list(repository.list_owners(connection))
        return _render_template(
            request,
            "owners.html",
            {
                "title": "ipocket - Owners",
                "owners": owners,
                "errors": errors,
                "form_state": {"name": name, "contact": contact or ""},
            },
            status_code=409,
            active_nav="owners",
        )

    return RedirectResponse(url="/ui/owners", status_code=303)


@router.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    asset_type: Optional[str] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    parsed_project_id = _parse_optional_int_query(project_id)
    parsed_owner_id = _parse_optional_int_query(owner_id)
    asset_type_value = _parse_optional_str(asset_type)
    asset_type_enum = (
        IPAssetType(asset_type_value)
        if asset_type_value in {asset.value for asset in IPAssetType}
        else None
    )
    assets = list(
        repository.list_active_ip_assets(
            connection,
            project_id=parsed_project_id,
            owner_id=parsed_owner_id,
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
    owners = list(repository.list_owners(connection))
    project_lookup = {project.id: project.name for project in projects}
    owner_lookup = {owner.id: owner.name for owner in owners}
    view_models = _build_asset_view_models(assets, project_lookup, owner_lookup)

    return _render_template(
        request,
        "ip_assets_list.html",
        {
            "title": "ipocket - IP Assets",
            "assets": view_models,
            "projects": projects,
            "owners": owners,
            "types": [asset.value for asset in IPAssetType],
            "filters": {
                "q": q or "",
                "project_id": parsed_project_id,
                "owner_id": parsed_owner_id,
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
    owners = list(repository.list_owners(connection))
    project_lookup = {project.id: project.name for project in projects}
    owner_lookup = {owner.id: owner.name for owner in owners}
    view_models = _build_asset_view_models(assets, project_lookup, owner_lookup)
    form_state = {
        "ip_address": view_models[0]["ip_address"] if view_models else "",
        "project_id": None,
        "owner_id": None,
    }
    return _render_template(
        request,
        "needs_assignment.html",
        {
            "title": "ipocket - Needs Assignment",
            "assets": view_models,
            "projects": projects,
            "owners": owners,
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
    owner_id = _parse_optional_int(form_data.get("owner_id"))

    errors = []
    if not ip_address:
        errors.append("Select an IP address.")
    if project_id is None and owner_id is None:
        errors.append("Assign at least one of Owner or Project.")

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
        owners = list(repository.list_owners(connection))
        project_lookup = {project.id: project.name for project in projects}
        owner_lookup = {owner.id: owner.name for owner in owners}
        view_models = _build_asset_view_models(assets, project_lookup, owner_lookup)
        return _render_template(
            request,
            "needs_assignment.html",
            {
                "title": "ipocket - Needs Assignment",
                "assets": view_models,
                "projects": projects,
                "owners": owners,
                "selected_filter": assignment_filter,
                "errors": errors,
                "form_state": {
                    "ip_address": ip_address,
                    "project_id": project_id,
                    "owner_id": owner_id,
                },
            },
            active_nav="needs-assignment",
        )

    repository.update_ip_asset(
        connection,
        ip_address=ip_address,
        project_id=project_id,
        owner_id=owner_id,
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
    owners = list(repository.list_owners(connection))
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
                "owner_id": "",
                "notes": "",
            },
            "projects": projects,
            "owners": owners,
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
    subnet = _parse_optional_str(form_data.get("subnet"))
    gateway = _parse_optional_str(form_data.get("gateway"))
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    owner_id = _parse_optional_int(form_data.get("owner_id"))
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    if not ip_address:
        errors.append("IP address is required.")
    if asset_type not in [asset.value for asset in IPAssetType]:
        errors.append("Asset type is required.")

    if ip_address:
        try:
            validate_ip_address(ip_address)
        except HTTPException as exc:
            errors.append(exc.detail)

    if errors:
        projects = list(repository.list_projects(connection))
        owners = list(repository.list_owners(connection))
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
                    "owner_id": owner_id or "",
                    "notes": notes or "",
                },
                "projects": projects,
                "owners": owners,
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
            asset_type=IPAssetType(asset_type),
            project_id=project_id,
            owner_id=owner_id,
            notes=notes,
        )
    except sqlite3.IntegrityError:
        errors.append("IP address already exists.")
        projects = list(repository.list_projects(connection))
        owners = list(repository.list_owners(connection))
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
                    "owner_id": owner_id or "",
                    "notes": notes or "",
                },
                "projects": projects,
                "owners": owners,
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
    owner_lookup = {
        owner.id: owner.name for owner in repository.list_owners(connection)
    }
    view_model = _build_asset_view_models([asset], project_lookup, owner_lookup)[0]
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
    owners = list(repository.list_owners(connection))
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
                "owner_id": asset.owner_id or "",
                "notes": asset.notes or "",
            },
            "projects": projects,
            "owners": owners,
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
    subnet = form_data.get("subnet")
    gateway = form_data.get("gateway")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    owner_id = _parse_optional_int(form_data.get("owner_id"))
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    if not subnet:
        errors.append("Subnet is required.")
    if not gateway:
        errors.append("Gateway is required.")
    if asset_type not in [asset.value for asset in IPAssetType]:
        errors.append("Asset type is required.")

    if errors:
        projects = list(repository.list_projects(connection))
        owners = list(repository.list_owners(connection))
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
                    "owner_id": owner_id or "",
                    "notes": notes or "",
                },
                "projects": projects,
                "owners": owners,
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
        asset_type=IPAssetType(asset_type),
        project_id=project_id,
        owner_id=owner_id,
        notes=notes,
    )
    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)


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
