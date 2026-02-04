from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import os
import secrets
import sqlite3
from typing import Optional
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app import auth, db, repository
from app.models import IPAsset, IPAssetType, UserRole

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

SESSION_COOKIE = "ipocket_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret").encode("utf-8")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class IPAssetCreate(BaseModel):
    ip_address: str
    subnet: str
    gateway: str
    asset_type: IPAssetType = Field(alias="type")
    project_id: Optional[int] = None
    owner_id: Optional[int] = None
    notes: Optional[str] = None


class IPAssetUpdate(BaseModel):
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    asset_type: Optional[IPAssetType] = Field(default=None, alias="type")
    project_id: Optional[int] = None
    owner_id: Optional[int] = None
    notes: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class OwnerCreate(BaseModel):
    name: str
    contact: Optional[str] = None


class OwnerUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None


def _asset_payload(asset: IPAsset) -> dict:
    return {
        "id": asset.id,
        "ip_address": asset.ip_address,
        "subnet": asset.subnet,
        "gateway": asset.gateway,
        "type": asset.asset_type.value,
        "project_id": asset.project_id,
        "owner_id": asset.owner_id,
        "notes": asset.notes,
        "archived": asset.archived,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def get_db_path() -> str:
    return os.getenv("IPAM_DB_PATH", "ipocket.db")


def get_connection():
    connection = db.connect(get_db_path())
    try:
        yield connection
    finally:
        connection.close()


def bootstrap_admin(connection) -> None:
    username = os.getenv("ADMIN_BOOTSTRAP_USERNAME")
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not username or not password:
        return
    if repository.count_users(connection) > 0:
        return
    repository.create_user(
        connection,
        username=username,
        hashed_password=auth.hash_password(password),
        role=UserRole.ADMIN,
    )


@app.on_event("startup")
def startup() -> None:
    connection = db.connect(get_db_path())
    try:
        db.init_db(connection)
        bootstrap_admin(connection)
    finally:
        connection.close()


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    connection=Depends(get_connection),
):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = auth.get_user_id_for_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = repository.get_user_by_id(connection, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_editor(user=Depends(get_current_user)):
    if user.role not in (UserRole.EDITOR, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


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


def validate_ip_address(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid IP address."
        ) from exc


def _metrics_payload(metrics: dict[str, int]) -> str:
    return "\n".join(
        [
            f"ipam_ip_total {metrics['total']}",
            f"ipam_ip_archived_total {metrics['archived_total']}",
            f"ipam_ip_unassigned_owner_total {metrics['unassigned_owner_total']}",
            f"ipam_ip_unassigned_project_total {metrics['unassigned_project_total']}",
            f"ipam_ip_unassigned_both_total {metrics['unassigned_both_total']}",
            "",
        ]
    )


def _is_unassigned(project_id: Optional[int], owner_id: Optional[int]) -> bool:
    return project_id is None or owner_id is None


def _display_name(value: Optional[str]) -> str:
    return value if value else "UNASSIGNED"


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


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
        project_name = project_lookup.get(asset.project_id, "")
        owner_name = owner_lookup.get(asset.owner_id, "")
        project_display = _display_name(project_name)
        owner_display = _display_name(owner_name)
        project_unassigned = project_display == "UNASSIGNED"
        owner_unassigned = owner_display == "UNASSIGNED"
        view_models.append(
            {
                "id": asset.id,
                "ip_address": asset.ip_address,
                "subnet": asset.subnet,
                "gateway": asset.gateway,
                "type": asset.asset_type.value,
                "project_name": project_display,
                "owner_name": owner_display,
                "notes": asset.notes or "",
                "unassigned": _is_unassigned(asset.project_id, asset.owner_id),
                "project_unassigned": project_unassigned,
                "owner_unassigned": owner_unassigned,
                "both_unassigned": project_unassigned and owner_unassigned,
            }
        )
    return view_models


def _assignment_badge(
    project_unassigned: bool, owner_unassigned: bool
) -> str:
    if project_unassigned and owner_unassigned:
        return '<span class="pill pill-danger">Missing owner + project</span>'
    if project_unassigned:
        return '<span class="pill pill-warning">Missing project</span>'
    if owner_unassigned:
        return '<span class="pill pill-danger">Missing owner</span>'
    return '<span class="pill pill-success">Assigned</span>'


def _project_tag(project_name: str, project_unassigned: bool) -> str:
    if project_unassigned:
        return '<span class="tag tag-warning">Unassigned</span>'
    return f'<span class="tag">{html.escape(project_name)}</span>'


def _owner_tag(owner_name: str, owner_unassigned: bool) -> str:
    if owner_unassigned:
        return '<span class="tag tag-danger">Unassigned</span>'
    return f'<span class="tag">{html.escape(owner_name)}</span>'


def _html_page(
    title: str,
    body: str,
    status_code: int = 200,
    show_nav: bool = True,
    active_nav: str = "",
) -> HTMLResponse:
    nav_html = ""
    if show_nav:
        nav_html = f"""
<div class="app-shell">
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-mark">ip</div>
      <div>
        <p class="brand-title">ipocket</p>
        <p class="brand-subtitle">IP inventory</p>
      </div>
    </div>
    <nav class="sidebar-nav">
      <a class="nav-link{' nav-link-active' if active_nav == 'ip-assets' else ''}" href="/ui/ip-assets">IP Assets</a>
      <a class="nav-link{' nav-link-active' if active_nav == 'needs-assignment' else ''}" href="/ui/ip-assets/needs-assignment">Needs Assignment</a>
      <a class="nav-link{' nav-link-active' if active_nav == 'projects' else ''}" href="/ui/projects">Projects</a>
      <a class="nav-link{' nav-link-active' if active_nav == 'owners' else ''}" href="/ui/owners">Owners</a>
    </nav>
    <div class="sidebar-footer">
      <p class="sidebar-note">Internal use only</p>
    </div>
  </aside>
  <div class="app-main">
    <header class="topbar">
      <div class="topbar-title">
        <span class="brand-pill">ipocket</span>
        <span class="topbar-subtitle">IP Asset Management</span>
      </div>
      <form method="post" action="/ui/logout">
        <button type="submit" class="btn btn-outline">Logout</button>
      </form>
    </header>
    <main class="content">
      {body}
    </main>
    <footer class="footer">
      <span>© 2024 ipocket Network Systems</span>
    </footer>
  </div>
</div>
"""
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="/static/app.css" />
  <title>{html.escape(title)}</title>
</head>
<body>
{nav_html if show_nav else body}
</body>
</html>
"""
    return HTMLResponse(content=content, status_code=status_code)


def _render_list_page(
    assets: list[dict],
    projects: list,
    owners: list,
    types: list[str],
    filters: dict,
) -> HTMLResponse:
    project_options = "\n".join(
        [
            f'<option value="{project.id}"'
            f'{" selected" if filters["project_id"] == project.id else ""}>{html.escape(project.name)}</option>'
            for project in projects
        ]
    )
    owner_options = "\n".join(
        [
            f'<option value="{owner.id}"'
            f'{" selected" if filters["owner_id"] == owner.id else ""}>{html.escape(owner.name)}</option>'
            for owner in owners
        ]
    )
    type_options = "\n".join(
        [
            f'<option value="{html.escape(asset_type)}"'
            f'{" selected" if filters["type"] == asset_type else ""}>{html.escape(asset_type)}</option>'
            for asset_type in types
        ]
    )
    rows = []
    for asset in assets:
        project_unassigned = asset["project_unassigned"]
        owner_unassigned = asset["owner_unassigned"]
        assignment_badge = _assignment_badge(project_unassigned, owner_unassigned)
        project_tag = _project_tag(asset["project_name"], project_unassigned)
        owner_tag = _owner_tag(asset["owner_name"], owner_unassigned)
        rows.append(
            f"""
            <tr>
              <td class="mono"><a href="/ui/ip-assets/{asset['id']}">{html.escape(asset['ip_address'])}</a></td>
              <td>{project_tag}</td>
              <td>{owner_tag}</td>
              <td class="muted">{html.escape(asset['type'])}</td>
              <td class="muted">{html.escape(asset['subnet'])}</td>
              <td>{assignment_badge}</td>
              <td class="muted">{html.escape(asset['notes'])}</td>
              <td><a class="link" href="/ui/ip-assets/{asset['id']}/edit">Edit</a></td>
            </tr>
            """
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="8" class="empty-state">No IP assets found.</td></tr>'
    )
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">Inventory</p>
      <h1>IP Assets</h1>
      <p class="subtitle">Manage and monitor network address assignments across all zones.</p>
    </div>
    <div class="header-actions">
      <a class="btn btn-primary" href="/ui/ip-assets/new">Add IP</a>
      <a class="btn btn-secondary" href="/ui/ip-assets/needs-assignment">Needs Assignment</a>
    </div>
  </section>
  <section class="card filter-card">
    <form class="filters-grid" method="get" action="/ui/ip-assets">
      <label class="field">
        <span>Search</span>
        <input class="input" type="text" name="q" value="{html.escape(filters['q'])}" placeholder="IP or notes" />
      </label>
      <label class="field">
        <span>Project</span>
        <select class="select" name="project_id">
          <option value="">All</option>
          {project_options}
        </select>
      </label>
      <label class="field">
        <span>Owner</span>
        <select class="select" name="owner_id">
          <option value="">All</option>
          {owner_options}
        </select>
      </label>
      <label class="field">
        <span>Type</span>
        <select class="select" name="type">
          <option value="">All</option>
          {type_options}
        </select>
      </label>
      <label class="checkbox-field">
        <input type="checkbox" name="unassigned-only" value="true" {"checked" if filters["unassigned_only"] else ""} />
        <span>Unassigned only</span>
      </label>
      <button class="btn btn-outline" type="submit">Apply filters</button>
    </form>
  </section>

  <section class="card table-card">
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th>IP address</th>
            <th>Project</th>
            <th>Owner</th>
            <th>Type</th>
            <th>Subnet</th>
            <th>Status</th>
            <th>Notes</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </section>
"""
    return _html_page("ipocket - IP Assets", body, active_nav="ip-assets")


def _render_needs_assignment_page(
    assets: list[dict],
    projects: list,
    owners: list,
    selected_filter: str,
    errors: list[str],
    form_state: dict,
) -> HTMLResponse:
    project_options = "\n".join(
        [
            f'<option value="{project.id}"'
            f'{" selected" if form_state["project_id"] == project.id else ""}>{html.escape(project.name)}</option>'
            for project in projects
        ]
    )
    owner_options = "\n".join(
        [
            f'<option value="{owner.id}"'
            f'{" selected" if form_state["owner_id"] == owner.id else ""}>{html.escape(owner.name)}</option>'
            for owner in owners
        ]
    )
    ip_options = "\n".join(
        [
            f'<option value="{html.escape(asset["ip_address"])}"'
            f'{" selected" if form_state["ip_address"] == asset["ip_address"] else ""}>{html.escape(asset["ip_address"])}</option>'
            for asset in assets
        ]
    )
    error_html = ""
    if errors:
        error_items = "\n".join([f"<li>{html.escape(error)}</li>" for error in errors])
        error_html = f"""
    <div class="alert alert-error">
      <p class="alert-title">Fix the following:</p>
      <ul>
        {error_items}
      </ul>
    </div>
"""
    rows = []
    for asset in assets:
        project_unassigned = asset["project_unassigned"]
        owner_unassigned = asset["owner_unassigned"]
        assignment_badge = _assignment_badge(project_unassigned, owner_unassigned)
        project_tag = _project_tag(asset["project_name"], project_unassigned)
        owner_tag = _owner_tag(asset["owner_name"], owner_unassigned)
        rows.append(
            f"""
            <tr>
              <td class="mono"><a href="/ui/ip-assets/{asset['id']}">{html.escape(asset['ip_address'])}</a></td>
              <td class="muted">{html.escape(asset['subnet'])}</td>
              <td>{assignment_badge}</td>
              <td>{owner_tag}</td>
              <td>{project_tag}</td>
              <td class="muted">{html.escape(asset['notes'])}</td>
            </tr>
            """
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="6" class="empty-state">No IP assets found.</td></tr>'
    )
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">Needs assignment</p>
      <h1>Assignment Inbox</h1>
      <p class="subtitle">Review unassigned IPs and quickly set owners or projects.</p>
    </div>
    <div class="header-actions">
      <a class="btn btn-secondary" href="/ui/ip-assets">Back to list</a>
    </div>
  </section>

  <section class="tabs">
    <a class="tab{' tab-active' if selected_filter == 'owner' else ''}" href="/ui/ip-assets/needs-assignment?filter=owner">Needs Owner</a>
    <a class="tab{' tab-active' if selected_filter == 'project' else ''}" href="/ui/ip-assets/needs-assignment?filter=project">Needs Project</a>
    <a class="tab{' tab-active' if selected_filter == 'both' else ''}" href="/ui/ip-assets/needs-assignment?filter=both">Needs Both</a>
  </section>

  <section class="card">
    <div class="card-header">
      <div>
        <h2>Quick assign</h2>
        <p class="subtitle">Choose an IP plus the Owner and/or Project to assign.</p>
      </div>
    </div>
    {error_html}
    <form class="form-grid" method="post" action="/ui/ip-assets/needs-assignment/assign?filter={html.escape(selected_filter)}">
      <label class="field">
        <span>IP address</span>
        <select class="select" name="ip_address">
          <option value="">Select an IP</option>
          {ip_options}
        </select>
      </label>
      <label class="field">
        <span>Project</span>
        <select class="select" name="project_id">
          <option value="">Leave unassigned</option>
          {project_options}
        </select>
      </label>
      <label class="field">
        <span>Owner</span>
        <select class="select" name="owner_id">
          <option value="">Leave unassigned</option>
          {owner_options}
        </select>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">Assign</button>
      </div>
    </form>
  </section>

  <section class="card table-card">
    <div class="card-header">
      <div>
        <h2>Matching IPs</h2>
        <p class="subtitle">Filtered list of IPs that need attention.</p>
      </div>
    </div>
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th>IP</th>
            <th>Subnet</th>
            <th>Status</th>
            <th>Owner</th>
            <th>Project</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </section>
"""
    return _html_page(
        "ipocket - Needs Assignment", body, active_nav="needs-assignment"
    )


def _render_detail_page(asset: dict) -> HTMLResponse:
    project_unassigned = asset["project_unassigned"]
    owner_unassigned = asset["owner_unassigned"]
    assignment_badge = _assignment_badge(project_unassigned, owner_unassigned)
    project_tag = _project_tag(asset["project_name"], project_unassigned)
    owner_tag = _owner_tag(asset["owner_name"], owner_unassigned)
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">IP asset</p>
      <h1>{html.escape(asset['ip_address'])}</h1>
      <p class="subtitle">Detailed assignment and configuration view.</p>
    </div>
    <div class="header-actions">
      <a class="btn btn-secondary" href="/ui/ip-assets">Back to list</a>
      <a class="btn btn-primary" href="/ui/ip-assets/{asset['id']}/edit">Edit</a>
    </div>
  </section>

  <section class="card detail-grid">
    <div class="detail-item">
      <p class="detail-label">Subnet</p>
      <p class="detail-value">{html.escape(asset['subnet'])}</p>
    </div>
    <div class="detail-item">
      <p class="detail-label">Gateway</p>
      <p class="detail-value">{html.escape(asset['gateway'])}</p>
    </div>
    <div class="detail-item">
      <p class="detail-label">Type</p>
      <p class="detail-value">{html.escape(asset['type'])}</p>
    </div>
    <div class="detail-item">
      <p class="detail-label">Project</p>
      <p class="detail-value">{project_tag}</p>
    </div>
    <div class="detail-item">
      <p class="detail-label">Owner</p>
      <p class="detail-value">{owner_tag}</p>
    </div>
    <div class="detail-item">
      <p class="detail-label">Assignment</p>
      <p class="detail-value">{assignment_badge}</p>
    </div>
    <div class="detail-item detail-item-wide">
      <p class="detail-label">Notes</p>
      <p class="detail-value">{html.escape(asset['notes'])}</p>
    </div>
  </section>

  <section class="card action-card">
    <h2>Actions (Editor/Admin)</h2>
    <div class="action-row">
      <a class="btn btn-outline" href="/ui/ip-assets/{asset['id']}/edit">Edit IP details</a>
      <form method="post" action="/ui/ip-assets/{asset['id']}/archive">
        <button class="btn btn-danger" type="submit">Archive IP</button>
      </form>
    </div>
  </section>
"""
    return _html_page("ipocket - IP Detail", body, active_nav="ip-assets")


def _render_form_page(
    asset: dict,
    projects: list,
    owners: list,
    types: list[str],
    errors: list[str],
    mode: str,
    status_code: int = 200,
) -> HTMLResponse:
    project_options = "\n".join(
        [
            f'<option value="{project.id}"'
            f'{" selected" if asset["project_id"] == project.id else ""}>{html.escape(project.name)}</option>'
            for project in projects
        ]
    )
    owner_options = "\n".join(
        [
            f'<option value="{owner.id}"'
            f'{" selected" if asset["owner_id"] == owner.id else ""}>{html.escape(owner.name)}</option>'
            for owner in owners
        ]
    )
    type_options = "\n".join(
        [
            f'<option value="{html.escape(asset_type)}"'
            f'{" selected" if asset["type"] == asset_type else ""}>{html.escape(asset_type)}</option>'
            for asset_type in types
        ]
    )
    error_html = ""
    if errors:
        error_items = "\n".join([f"<li>{html.escape(error)}</li>" for error in errors])
        error_html = f"""
    <div class="alert alert-error">
      <p class="alert-title">Fix the following:</p>
      <ul>
        {error_items}
      </ul>
    </div>
"""
    action_url = (
        "/ui/ip-assets/new"
        if mode == "create"
        else f"/ui/ip-assets/{asset['id']}/edit"
    )
    read_only = "readonly" if mode == "edit" else ""
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">{'Create' if mode == 'create' else 'Edit'} IP</p>
      <h1>{'Add IP asset' if mode == 'create' else 'Edit IP asset'}</h1>
      <p class="subtitle">Provide addressing, ownership, and metadata.</p>
    </div>
    <div class="header-actions">
      <a class="btn btn-secondary" href="/ui/ip-assets">Back to list</a>
    </div>
  </section>

  <section class="card">
    {error_html}
    <form class="form-grid form-grid-two" method="post" action="{action_url}">
      <label class="field">
        <span>IP address</span>
        <input class="input" type="text" name="ip_address" value="{html.escape(asset['ip_address'])}" {read_only} />
      </label>
      <label class="field">
        <span>Subnet</span>
        <input class="input" type="text" name="subnet" value="{html.escape(asset['subnet'])}" />
      </label>
      <label class="field">
        <span>Gateway</span>
        <input class="input" type="text" name="gateway" value="{html.escape(asset['gateway'])}" />
      </label>
      <label class="field">
        <span>Type</span>
        <select class="select" name="type">
          {type_options}
        </select>
      </label>
      <label class="field">
        <span>Project</span>
        <select class="select" name="project_id">
          <option value="">UNASSIGNED</option>
          {project_options}
        </select>
      </label>
      <label class="field">
        <span>Owner</span>
        <select class="select" name="owner_id">
          <option value="">UNASSIGNED</option>
          {owner_options}
        </select>
      </label>
      <label class="field field-span">
        <span>Notes</span>
        <textarea class="textarea" name="notes" rows="4">{html.escape(asset['notes'])}</textarea>
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">{'Create' if mode == 'create' else 'Save changes'}</button>
      </div>
    </form>
  </section>
"""
    return _html_page(
        f"ipocket - {'Add IP' if mode == 'create' else 'Edit IP'}",
        body,
        status_code=status_code,
        active_nav="ip-assets",
    )


def _render_projects_page(
    projects: list,
    errors: list[str],
    form_state: dict,
    status_code: int = 200,
) -> HTMLResponse:
    error_html = ""
    if errors:
        error_items = "\n".join([f"<li>{html.escape(error)}</li>" for error in errors])
        error_html = f"""
    <div class="alert alert-error">
      <p class="alert-title">Fix the following:</p>
      <ul>
        {error_items}
      </ul>
    </div>
"""
    rows = []
    for project in projects:
        rows.append(
            f"""
            <tr>
              <td>{html.escape(project.name)}</td>
              <td>{html.escape(project.description or '')}</td>
            </tr>
            """
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="2" class="empty-state">No projects yet.</td></tr>'
    )
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">Library</p>
      <h1>Projects</h1>
      <p class="subtitle">Manage project names used in IP assignments.</p>
    </div>
  </section>

  <section class="card">
    <div class="card-header">
      <div>
        <h2>Create project</h2>
        <p class="subtitle">Add new project labels for IP assignments.</p>
      </div>
    </div>
    {error_html}
    <form method="post" action="/ui/projects" class="form-grid form-grid-two">
      <label class="field">
        <span>Name</span>
        <input class="input" type="text" name="name" value="{html.escape(form_state['name'])}" required />
      </label>
      <label class="field">
        <span>Description</span>
        <input class="input" type="text" name="description" value="{html.escape(form_state['description'])}" />
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">Create project</button>
      </div>
    </form>
  </section>

  <section class="card table-card">
    <div class="card-header">
      <div>
        <h2>Existing projects</h2>
        <p class="subtitle">Keep the catalog of project ownership current.</p>
      </div>
    </div>
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </section>
"""
    return _html_page(
        "ipocket - Projects",
        body,
        status_code=status_code,
        active_nav="projects",
    )


def _render_owners_page(
    owners: list,
    errors: list[str],
    form_state: dict,
    status_code: int = 200,
) -> HTMLResponse:
    error_html = ""
    if errors:
        error_items = "\n".join([f"<li>{html.escape(error)}</li>" for error in errors])
        error_html = f"""
    <div class="alert alert-error">
      <p class="alert-title">Fix the following:</p>
      <ul>
        {error_items}
      </ul>
    </div>
"""
    rows = []
    for owner in owners:
        rows.append(
            f"""
            <tr>
              <td>{html.escape(owner.name)}</td>
              <td>{html.escape(owner.contact or '')}</td>
            </tr>
            """
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="2" class="empty-state">No owners yet.</td></tr>'
    )
    body = f"""
  <section class="page-header">
    <div>
      <p class="eyebrow">Directory</p>
      <h1>Owners</h1>
      <p class="subtitle">Track teams or individuals responsible for IPs.</p>
    </div>
  </section>

  <section class="card">
    <div class="card-header">
      <div>
        <h2>Create owner</h2>
        <p class="subtitle">Add responsible teams or contacts.</p>
      </div>
    </div>
    {error_html}
    <form method="post" action="/ui/owners" class="form-grid form-grid-two">
      <label class="field">
        <span>Name</span>
        <input class="input" type="text" name="name" value="{html.escape(form_state['name'])}" required />
      </label>
      <label class="field">
        <span>Contact</span>
        <input class="input" type="text" name="contact" value="{html.escape(form_state['contact'])}" />
      </label>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">Create owner</button>
      </div>
    </form>
  </section>

  <section class="card table-card">
    <div class="card-header">
      <div>
        <h2>Existing owners</h2>
        <p class="subtitle">Maintain the owner directory for assignments.</p>
      </div>
    </div>
    <div class="table-wrapper">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Contact</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </section>
"""
    return _html_page(
        "ipocket - Owners", body, status_code=status_code, active_nav="owners"
    )


async def _parse_form_data(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode())
    return {key: values[0] for key, values in parsed.items()}


@app.get("/health")
def health_check() -> Response:
    return Response(content="ok", media_type="text/plain")


@app.get("/metrics")
def metrics(connection=Depends(get_connection)) -> Response:
    metrics_payload = repository.get_ip_asset_metrics(connection)
    return Response(
        content=_metrics_payload(metrics_payload), media_type="text/plain"
    )


@app.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, connection=Depends(get_connection)) -> TokenResponse:
    user = repository.get_user_by_username(connection, request.username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not auth.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = auth.create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/ip-assets")
def create_ip_asset(
    payload: IPAssetCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    validate_ip_address(payload.ip_address)
    try:
        asset = repository.create_ip_asset(
            connection,
            ip_address=payload.ip_address,
            subnet=payload.subnet,
            gateway=payload.gateway,
            asset_type=payload.asset_type,
            project_id=payload.project_id,
            owner_id=payload.owner_id,
            notes=payload.notes,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IP address already exists.",
        ) from exc
    return _asset_payload(asset)


@app.get("/ip-assets")
def list_ip_assets(
    project_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    assets = repository.list_active_ip_assets(
        connection,
        project_id=project_id,
        owner_id=owner_id,
        asset_type=asset_type,
        unassigned_only=unassigned_only,
    )
    return [_asset_payload(asset) for asset in assets]


@app.get("/ip-assets/{ip_address}")
def get_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
):
    asset = repository.get_ip_asset_by_ip(connection, ip_address)
    if asset is None or asset.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _asset_payload(asset)


@app.patch("/ip-assets/{ip_address}")
def update_ip_asset(
    ip_address: str,
    payload: IPAssetUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    updated = repository.update_ip_asset(
        connection,
        ip_address=ip_address,
        subnet=payload.subnet,
        gateway=payload.gateway,
        asset_type=payload.asset_type,
        project_id=payload.project_id,
        owner_id=payload.owner_id,
        notes=payload.notes,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _asset_payload(updated)


@app.post("/ip-assets/{ip_address}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_ip_asset(
    ip_address: str,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    asset = repository.get_ip_asset_by_ip(connection, ip_address)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    repository.archive_ip_asset(connection, ip_address)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/projects")
def create_project(
    payload: ProjectCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    project = repository.create_project(
        connection, name=payload.name, description=payload.description
    )
    return {"id": project.id, "name": project.name, "description": project.description}


@app.get("/projects")
def list_projects(connection=Depends(get_connection)):
    projects = repository.list_projects(connection)
    return [
        {"id": project.id, "name": project.name, "description": project.description}
        for project in projects
    ]


@app.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    project = repository.update_project(
        connection,
        project_id=project_id,
        name=payload.name,
        description=payload.description,
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": project.id, "name": project.name, "description": project.description}


@app.post("/owners")
def create_owner(
    payload: OwnerCreate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    owner = repository.create_owner(
        connection, name=payload.name, contact=payload.contact
    )
    return {"id": owner.id, "name": owner.name, "contact": owner.contact}


@app.get("/owners")
def list_owners(connection=Depends(get_connection)):
    owners = repository.list_owners(connection)
    return [
        {"id": owner.id, "name": owner.name, "contact": owner.contact}
        for owner in owners
    ]


@app.patch("/owners/{owner_id}")
def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    connection=Depends(get_connection),
    _user=Depends(require_editor),
):
    owner = repository.update_owner(
        connection,
        owner_id=owner_id,
        name=payload.name,
        contact=payload.contact,
    )
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"id": owner.id, "name": owner.name, "contact": owner.contact}


@app.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    return RedirectResponse(url="/ui/ip-assets")


@app.get("/ui/login", response_class=HTMLResponse)
def ui_login_form(request: Request) -> HTMLResponse:
    body = """
<main class="login-page">
  <div class="login-card">
    <div class="login-header">
      <div class="login-icon">ip</div>
      <h1>ipocket</h1>
      <p>Internal IP asset management</p>
    </div>
    <form method="post" action="/ui/login" class="login-form">
      <label class="field">
        <span>Username</span>
        <input class="input" type="text" name="username" placeholder="Enter your username" required />
      </label>
      <label class="field">
        <span>Password</span>
        <input class="input" type="password" name="password" placeholder="Enter your password" required />
      </label>
      <button class="btn btn-primary btn-block" type="submit">Login</button>
    </form>
    <p class="login-footnote">Authorized personnel only</p>
  </div>
</main>
"""
    return _html_page("ipocket - Login", body, show_nav=False)


@app.post("/ui/login", response_class=HTMLResponse)
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
        body = """
<main class="login-page">
  <div class="login-card">
    <div class="login-header">
      <div class="login-icon">ip</div>
      <h1>ipocket</h1>
      <p>Internal IP asset management</p>
    </div>
    <div class="alert alert-error">
      <p class="alert-title">Invalid username or password.</p>
    </div>
    <form method="post" action="/ui/login" class="login-form">
      <label class="field">
        <span>Username</span>
        <input class="input" type="text" name="username" placeholder="Enter your username" required />
      </label>
      <label class="field">
        <span>Password</span>
        <input class="input" type="password" name="password" placeholder="Enter your password" required />
      </label>
      <button class="btn btn-primary btn-block" type="submit">Login</button>
    </form>
    <p class="login-footnote">Authorized personnel only</p>
  </div>
</main>
"""
        return _html_page("ipocket - Login", body, status_code=401, show_nav=False)

    response = RedirectResponse(url="/ui/ip-assets", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session_value(str(user.id)),
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/ui/logout")
def ui_logout(request: Request) -> Response:
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/ui/projects", response_class=HTMLResponse)
def ui_list_projects(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    projects = list(repository.list_projects(connection))
    return _render_projects_page(
        projects=projects,
        errors=[],
        form_state={"name": "", "description": ""},
    )


@app.post("/ui/projects", response_class=HTMLResponse)
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
        return _render_projects_page(
            projects=projects,
            errors=errors,
            form_state={"name": name, "description": description or ""},
            status_code=400,
        )

    try:
        repository.create_project(connection, name=name, description=description)
    except sqlite3.IntegrityError:
        errors.append("Project name already exists.")
        projects = list(repository.list_projects(connection))
        return _render_projects_page(
            projects=projects,
            errors=errors,
            form_state={"name": name, "description": description or ""},
            status_code=409,
        )

    return RedirectResponse(url="/ui/projects", status_code=303)


@app.get("/ui/owners", response_class=HTMLResponse)
def ui_list_owners(
    request: Request,
    connection=Depends(get_connection),
) -> HTMLResponse:
    owners = list(repository.list_owners(connection))
    return _render_owners_page(
        owners=owners,
        errors=[],
        form_state={"name": "", "contact": ""},
    )


@app.post("/ui/owners", response_class=HTMLResponse)
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
        return _render_owners_page(
            owners=owners,
            errors=errors,
            form_state={"name": name, "contact": contact or ""},
            status_code=400,
        )

    try:
        repository.create_owner(connection, name=name, contact=contact)
    except sqlite3.IntegrityError:
        errors.append("Owner name already exists.")
        owners = list(repository.list_owners(connection))
        return _render_owners_page(
            owners=owners,
            errors=errors,
            form_state={"name": name, "contact": contact or ""},
            status_code=409,
        )

    return RedirectResponse(url="/ui/owners", status_code=303)


@app.get("/ui/ip-assets", response_class=HTMLResponse)
def ui_list_ip_assets(
    request: Request,
    q: Optional[str] = None,
    project_id: Optional[int] = None,
    owner_id: Optional[int] = None,
    asset_type: Optional[IPAssetType] = Query(default=None, alias="type"),
    unassigned_only: bool = Query(default=False, alias="unassigned-only"),
    connection=Depends(get_connection),
):
    assets = list(
        repository.list_active_ip_assets(
            connection,
            project_id=project_id,
            owner_id=owner_id,
            asset_type=asset_type,
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

    context = {
        "assets": view_models,
        "projects": projects,
        "owners": owners,
        "types": [asset.value for asset in IPAssetType],
        "filters": {
            "q": q or "",
            "project_id": project_id,
            "owner_id": owner_id,
            "type": asset_type.value if asset_type else "",
            "unassigned_only": unassigned_only,
        },
    }
    return _render_list_page(**context)


@app.get("/ui/ip-assets/needs-assignment", response_class=HTMLResponse)
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
    return _render_needs_assignment_page(
        assets=view_models,
        projects=projects,
        owners=owners,
        selected_filter=assignment_filter,
        errors=[],
        form_state=form_state,
    )


@app.post("/ui/ip-assets/needs-assignment/assign", response_class=HTMLResponse)
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
            repository.list_ip_assets_needing_assignment(connection, assignment_filter)
        )
        projects = list(repository.list_projects(connection))
        owners = list(repository.list_owners(connection))
        project_lookup = {project.id: project.name for project in projects}
        owner_lookup = {owner.id: owner.name for owner in owners}
        view_models = _build_asset_view_models(assets, project_lookup, owner_lookup)
        return _render_needs_assignment_page(
            assets=view_models,
            projects=projects,
            owners=owners,
            selected_filter=assignment_filter,
            errors=errors,
            form_state={
                "ip_address": ip_address,
                "project_id": project_id,
                "owner_id": owner_id,
            },
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


@app.get("/ui/ip-assets/new", response_class=HTMLResponse)
def ui_add_ip_form(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    projects = list(repository.list_projects(connection))
    owners = list(repository.list_owners(connection))
    return _render_form_page(
        asset={
            "id": None,
            "ip_address": "",
            "subnet": "",
            "gateway": "",
            "type": IPAssetType.VM.value,
            "project_id": "",
            "owner_id": "",
            "notes": "",
        },
        projects=projects,
        owners=owners,
        types=[asset.value for asset in IPAssetType],
        errors=[],
        mode="create",
    )


@app.post("/ui/ip-assets/new", response_class=HTMLResponse)
async def ui_add_ip_submit(
    request: Request,
    connection=Depends(get_connection),
    _user=Depends(require_ui_editor),
):
    form_data = await _parse_form_data(request)
    ip_address = form_data.get("ip_address")
    subnet = form_data.get("subnet")
    gateway = form_data.get("gateway")
    asset_type = form_data.get("type")
    project_id = _parse_optional_int(form_data.get("project_id"))
    owner_id = _parse_optional_int(form_data.get("owner_id"))
    notes = _parse_optional_str(form_data.get("notes"))

    errors = []
    if not ip_address:
        errors.append("IP address is required.")
    if not subnet:
        errors.append("Subnet is required.")
    if not gateway:
        errors.append("Gateway is required.")
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
        return _render_form_page(
            asset={
                "id": None,
                "ip_address": ip_address or "",
                "subnet": subnet or "",
                "gateway": gateway or "",
                "type": asset_type or "",
                "project_id": project_id or "",
                "owner_id": owner_id or "",
                "notes": notes or "",
            },
            projects=projects,
            owners=owners,
            types=[asset.value for asset in IPAssetType],
            errors=errors,
            mode="create",
            status_code=400,
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
        return _render_form_page(
            asset={
                "id": None,
                "ip_address": ip_address or "",
                "subnet": subnet or "",
                "gateway": gateway or "",
                "type": asset_type or "",
                "project_id": project_id or "",
                "owner_id": owner_id or "",
                "notes": notes or "",
            },
            projects=projects,
            owners=owners,
            types=[asset.value for asset in IPAssetType],
            errors=errors,
            mode="create",
            status_code=409,
        )

    return RedirectResponse(url=f"/ui/ip-assets/{asset.id}", status_code=303)


@app.get("/ui/ip-assets/{asset_id}", response_class=HTMLResponse)
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
    return _render_detail_page(view_model)


@app.get("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
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
    return _render_form_page(
        asset={
            "id": asset.id,
            "ip_address": asset.ip_address,
            "subnet": asset.subnet,
            "gateway": asset.gateway,
            "type": asset.asset_type.value,
            "project_id": asset.project_id or "",
            "owner_id": asset.owner_id or "",
            "notes": asset.notes or "",
        },
        projects=projects,
        owners=owners,
        types=[asset.value for asset in IPAssetType],
        errors=[],
        mode="edit",
    )


@app.post("/ui/ip-assets/{asset_id}/edit", response_class=HTMLResponse)
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
        return _render_form_page(
            asset={
                "id": asset.id,
                "ip_address": asset.ip_address,
                "subnet": subnet or "",
                "gateway": gateway or "",
                "type": asset_type or "",
                "project_id": project_id or "",
                "owner_id": owner_id or "",
                "notes": notes or "",
            },
            projects=projects,
            owners=owners,
            types=[asset.value for asset in IPAssetType],
            errors=errors,
            mode="edit",
            status_code=400,
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


@app.post("/ui/ip-assets/{asset_id}/archive")
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
