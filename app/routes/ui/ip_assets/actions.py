from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from typing import Optional

import app.routes.ui.ip_assets as ip_assets_routes

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app import repository
from app.dependencies import get_connection
from app.models import IPAssetType
from app.routes.ui.utils import (
    _append_query_param,
    _normalize_asset_type,
    _parse_optional_str,
    require_ui_editor,
)

from .helpers import _delete_requires_exact_ip, _parse_selected_tags

router = APIRouter()

_TOAST_QUERY_KEYS = {"bulk-error", "bulk-success", "delete-error", "delete-success"}


def _strip_toast_query_params(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in _TOAST_QUERY_KEYS:
        query.pop(key, None)
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


@router.post("/ui/ip-assets/bulk-edit", response_class=HTMLResponse)
async def ui_bulk_edit_ip_assets(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(require_ui_editor),
):
    form = await request.form()
    asset_ids_raw = form.getlist("asset_ids")
    return_to = _strip_toast_query_params(form.get("return_to") or "/ui/ip-assets")
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
            project_id_value = ip_assets_routes._parse_optional_int(project_selection)
            if project_id_value is None:
                errors.append("Select a valid project.")
            elif repository.get_project_by_id(connection, project_id_value) is None:
                errors.append("Selected project does not exist.")

    tags_to_add_raw = [str(tag) for tag in form.getlist("tags")]
    tags_to_add, tag_errors = _parse_selected_tags(connection, tags_to_add_raw)
    errors.extend(tag_errors)
    remove_tags_raw = [str(tag) for tag in form.getlist("remove_tags")]
    tags_to_remove, remove_tag_errors = _parse_selected_tags(
        connection, remove_tags_raw
    )
    errors.extend(remove_tag_errors)
    notes_mode = str(form.get("notes_mode") or "").strip().lower()
    set_notes = False
    notes_value: Optional[str] = None
    if notes_mode:
        if notes_mode == "set":
            set_notes = True
            notes_value = _parse_optional_str(form.get("notes"))
            if notes_value is None:
                errors.append("Enter notes to overwrite, or choose clear notes.")
        elif notes_mode == "clear":
            set_notes = True
            notes_value = None
        else:
            errors.append("Select a valid notes action.")

    if (
        not asset_type_enum
        and not set_project_id
        and not set_notes
        and not tags_to_add
        and not tags_to_remove
    ):
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
        notes=notes_value,
        set_notes=set_notes,
        tags_to_add=tags_to_add,
        tags_to_remove=tags_to_remove,
        current_user=user,
    )
    success_message = f"Updated {len(updated_assets)} IP assets."
    return RedirectResponse(
        url=_append_query_param(return_to, "bulk-success", success_message),
        status_code=303,
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
        return JSONResponse(
            {"error": "Auto-host creation is only available for BMC assets."},
            status_code=400,
        )
    if asset.host_id is not None:
        return JSONResponse(
            {"error": "This IP is already assigned to a host."}, status_code=409
        )

    host_name = f"server_{asset.ip_address}"
    host = repository.get_host_by_name(connection, host_name)
    if host is None:
        host = repository.create_host(
            connection, name=host_name, notes=None, vendor=None
        )

    repository.update_ip_asset(
        connection,
        ip_address=asset.ip_address,
        host_id=host.id,
        current_user=user,
    )

    return JSONResponse({"host_id": host.id, "host_name": host.name})


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
    from app.routes.ui.utils import _render_template

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

    form_data = await request.form()
    return_to = _strip_toast_query_params(
        str(form_data.get("return_to") or "/ui/ip-assets").strip()
    )
    confirmation_ack_raw = (
        str(form_data.get("confirm_delete_ack") or "").strip().lower()
    )
    confirmation_ack = bool(
        confirmation_ack_raw and confirmation_ack_raw not in {"0", "false", "off", "no"}
    )
    confirm_ip = str(form_data.get("confirm_ip") or "").strip()
    tags_map = repository.list_tags_for_ip_assets(connection, [asset.id])
    tag_names = tags_map.get(asset.id, [])
    requires_exact_ip = _delete_requires_exact_ip(asset, tag_names)

    errors: list[str] = []
    if not confirmation_ack:
        errors.append("Confirm that this delete cannot be undone.")
    if requires_exact_ip and confirm_ip != asset.ip_address:
        errors.append("Type the exact IP address to delete this high-risk asset.")

    wants_json = "application/json" in (request.headers.get("accept") or "")
    if errors:
        if wants_json:
            return JSONResponse({"error": errors[0]}, status_code=400)
        return RedirectResponse(
            url=_append_query_param(
                return_to if return_to.startswith("/") else "/ui/ip-assets",
                "delete-error",
                errors[0],
            ),
            status_code=303,
        )

    repository.delete_ip_asset(connection, asset.ip_address, current_user=user)
    if wants_json:
        return JSONResponse(
            {
                "message": f"Deleted {asset.ip_address}.",
                "asset_id": asset.id,
                "ip_address": asset.ip_address,
            }
        )
    success_url = _append_query_param(
        return_to if return_to.startswith("/") else "/ui/ip-assets",
        "delete-success",
        f"Deleted {asset.ip_address}.",
    )
    return RedirectResponse(url=success_url, status_code=303)


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
