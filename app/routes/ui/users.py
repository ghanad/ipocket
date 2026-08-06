from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response

from app import repository
from app.dependencies import get_connection
from .user_management import (
    UserMutationError,
    create_managed_user,
    delete_managed_user,
    update_managed_user,
    user_payload,
)
from .utils import (
    _parse_form_data,
    _render_template,
    _redirect_with_flash,
    require_ui_superuser,
)

router = APIRouter()


async def _read_json_object(request: Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON request.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="JSON object is required.")
    return payload


def _string_field(payload: dict[str, object], name: str, *, default: str = "") -> str:
    value = payload.get(name, default)
    if not isinstance(value, str):
        raise HTTPException(
            status_code=422,
            detail=f"{name.replace('_', ' ').capitalize()} must be text.",
        )
    return value


def _bool_field(
    payload: dict[str, object], name: str, *, default: bool | None = None
) -> bool:
    value = payload.get(name, default)
    if not isinstance(value, bool):
        raise HTTPException(
            status_code=422,
            detail=f"{name.replace('_', ' ').capitalize()} must be true or false.",
        )
    return value


def _legacy_error_status(error: UserMutationError) -> int:
    return 409 if error.status_code == 409 else 400


def _legacy_error_page(
    request: Request,
    error: UserMutationError,
    *,
    mode: str,
    form: dict[str, str],
) -> HTMLResponse:
    return _render_template(
        request,
        "users.html",
        {
            "title": "ipocket - Users",
            "legacy_errors": [error.message],
            "legacy_mode": mode,
            "legacy_form": form,
        },
        active_nav="users",
        status_code=_legacy_error_status(error),
    )


@router.get("/ui/users", response_class=HTMLResponse)
def ui_users(
    request: Request,
    connection=Depends(get_connection),
    _superuser=Depends(require_ui_superuser),
) -> HTMLResponse:
    return _render_template(
        request,
        "users.html",
        {"title": "ipocket - Users"},
        active_nav="users",
    )


@router.get("/api/ui/users")
def list_users_for_ui(
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
):
    return {
        "actor": {
            "id": actor.id,
            "username": actor.username,
            "role": actor.role.value,
        },
        "users": [
            user_payload(connection, actor, user)
            for user in repository.list_users(connection)
        ],
    }


@router.post("/api/ui/users", status_code=status.HTTP_201_CREATED)
async def create_user_for_ui(
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
):
    payload = await _read_json_object(request)
    try:
        created = create_managed_user(
            connection,
            actor,
            username=_string_field(payload, "username"),
            password=_string_field(payload, "password"),
            can_edit=_bool_field(payload, "can_edit", default=True),
            is_active=_bool_field(payload, "is_active", default=True),
        )
    except UserMutationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return user_payload(connection, actor, created)


@router.patch("/api/ui/users/{user_id}")
async def update_user_for_ui(
    user_id: int,
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
):
    target = repository.get_user_by_id(connection, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    payload = await _read_json_object(request)
    try:
        result = update_managed_user(
            connection,
            actor,
            target,
            can_edit=_bool_field(payload, "can_edit"),
            is_active=_bool_field(payload, "is_active"),
            password=_string_field(payload, "password"),
        )
    except UserMutationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {
        "user": user_payload(connection, actor, result.user),
        "changed": result.changed,
    }


@router.delete("/api/ui/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_for_ui(
    user_id: int,
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
) -> Response:
    target = repository.get_user_by_id(connection, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    payload = await _read_json_object(request)
    try:
        delete_managed_user(
            connection,
            actor,
            target,
            confirm_username=_string_field(payload, "confirm_username"),
        )
    except UserMutationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ui/users", response_class=HTMLResponse)
async def ui_create_user(
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
) -> HTMLResponse:
    form_data = await _parse_form_data(request)
    username = (form_data.get("username") or "").strip()
    password = form_data.get("password") or ""
    can_edit = form_data.get("can_edit") == "1"
    is_active = form_data.get("is_active") == "1"

    try:
        create_managed_user(
            connection,
            actor,
            username=username,
            password=password,
            can_edit=can_edit,
            is_active=is_active,
        )
    except UserMutationError as error:
        return _legacy_error_page(
            request,
            error,
            mode="create",
            form={
                "username": username,
                "can_edit": "1" if can_edit else "",
                "is_active": "1" if is_active else "",
            },
        )
    return _redirect_with_flash(
        request,
        "/ui/users",
        "User created.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/users/{user_id}/edit", response_class=HTMLResponse)
async def ui_edit_user(
    user_id: int,
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
) -> Response:
    form_data = await _parse_form_data(request)
    password = form_data.get("password") or ""
    can_edit = form_data.get("can_edit") == "1"
    is_active = form_data.get("is_active") == "1"

    target = repository.get_user_by_id(connection, user_id)
    if target is None:
        return Response(status_code=404)

    try:
        update_managed_user(
            connection,
            actor,
            target,
            can_edit=can_edit,
            is_active=is_active,
            password=password,
        )
    except UserMutationError as error:
        return _legacy_error_page(
            request,
            error,
            mode="edit",
            form={
                "id": str(target.id),
                "username": target.username,
                "can_edit": "1" if can_edit else "",
                "is_active": "1" if is_active else "",
                "role": target.role.value,
            },
        )

    return _redirect_with_flash(
        request,
        "/ui/users",
        "User updated.",
        message_type="success",
        status_code=303,
    )


@router.post("/ui/users/{user_id}/delete", response_class=HTMLResponse)
async def ui_delete_user(
    user_id: int,
    request: Request,
    connection=Depends(get_connection),
    actor=Depends(require_ui_superuser),
) -> Response:
    form_data = await _parse_form_data(request)
    confirm_username = (form_data.get("confirm_username") or "").strip()

    target = repository.get_user_by_id(connection, user_id)
    if target is None:
        return Response(status_code=404)

    try:
        delete_managed_user(
            connection,
            actor,
            target,
            confirm_username=confirm_username,
        )
    except UserMutationError as error:
        return _legacy_error_page(
            request,
            error,
            mode="delete",
            form={
                "id": str(target.id),
                "username": target.username,
                "confirm_username": confirm_username,
            },
        )

    return _redirect_with_flash(
        request,
        "/ui/users",
        "User deleted.",
        message_type="success",
        status_code=303,
    )
