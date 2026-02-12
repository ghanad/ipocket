from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app import auth, repository
from app.dependencies import get_connection
from app.models import UserRole
from .utils import (
    _parse_form_data,
    _render_template,
    _redirect_with_flash,
    require_ui_superuser,
)

router = APIRouter()


def _users_template_context(
    connection,
    *,
    create_errors: list[str] | None = None,
    create_form: dict[str, str] | None = None,
    edit_errors: list[str] | None = None,
    edit_form: dict[str, str] | None = None,
    delete_errors: list[str] | None = None,
    delete_form: dict[str, str] | None = None,
):
    users = list(repository.list_users(connection))
    return {
        "title": "ipocket - Users",
        "users": users,
        "create_errors": create_errors or [],
        "create_form": create_form
        or {
            "username": "",
            "password": "",
            "can_edit": "1",
            "is_active": "1",
        },
        "edit_errors": edit_errors or [],
        "edit_form": edit_form
        or {
            "id": "",
            "username": "",
            "password": "",
            "can_edit": "",
            "is_active": "",
            "role": "",
        },
        "delete_errors": delete_errors or [],
        "delete_form": delete_form
        or {
            "id": "",
            "username": "",
            "confirm_username": "",
        },
    }


def _audit_user_change(connection, actor, target, action: str, changes: str) -> None:
    repository.create_audit_log(
        connection,
        user=actor,
        action=action,
        target_type="USER",
        target_id=target.id,
        target_label=target.username,
        changes=changes,
    )
    connection.commit()


def _can_deactivate_superuser(connection, user) -> bool:
    if user.role != UserRole.SUPERUSER:
        return True
    active_superusers = repository.count_active_users_by_role(
        connection, UserRole.SUPERUSER
    )
    return active_superusers > 1


def _can_delete_user(connection, actor, target) -> tuple[bool, str]:
    if target.id == actor.id:
        return False, "You cannot delete your own account."
    if target.role == UserRole.SUPERUSER and not _can_deactivate_superuser(
        connection, target
    ):
        return False, "Cannot delete the last active superuser."
    return True, ""


@router.get("/ui/users", response_class=HTMLResponse)
def ui_users(
    request: Request,
    connection=Depends(get_connection),
    _superuser=Depends(require_ui_superuser),
) -> HTMLResponse:
    return _render_template(
        request,
        "users.html",
        _users_template_context(connection),
        active_nav="users",
    )


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

    errors: list[str] = []
    if not username:
        errors.append("Username is required.")
    if not password:
        errors.append("Password is required.")

    if errors:
        return _render_template(
            request,
            "users.html",
            _users_template_context(
                connection,
                create_errors=errors,
                create_form={
                    "username": username,
                    "password": "",
                    "can_edit": "1" if can_edit else "",
                    "is_active": "1" if is_active else "",
                },
            ),
            active_nav="users",
            status_code=400,
        )

    role = UserRole.EDITOR if can_edit else UserRole.VIEWER
    try:
        created = repository.create_user(
            connection,
            username=username,
            hashed_password=auth.hash_password(password),
            role=role,
            is_active=is_active,
        )
    except sqlite3.IntegrityError:
        return _render_template(
            request,
            "users.html",
            _users_template_context(
                connection,
                create_errors=["Username already exists."],
                create_form={
                    "username": username,
                    "password": "",
                    "can_edit": "1" if can_edit else "",
                    "is_active": "1" if is_active else "",
                },
            ),
            active_nav="users",
            status_code=409,
        )

    _audit_user_change(
        connection,
        actor,
        created,
        action="CREATE",
        changes=f"Created user (role={created.role.value}, is_active={int(created.is_active)})",
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

    errors: list[str] = []
    if target.role == UserRole.SUPERUSER and can_edit is False:
        errors.append("Superuser edit access cannot be changed.")
    if not is_active and not _can_deactivate_superuser(connection, target):
        errors.append("Cannot deactivate the last active superuser.")

    if errors:
        return _render_template(
            request,
            "users.html",
            _users_template_context(
                connection,
                edit_errors=errors,
                edit_form={
                    "id": str(target.id),
                    "username": target.username,
                    "password": "",
                    "can_edit": "1" if can_edit else "",
                    "is_active": "1" if is_active else "",
                    "role": target.role.value,
                },
            ),
            active_nav="users",
            status_code=400,
        )

    change_lines: list[str] = []

    updated_user = target
    if target.role != UserRole.SUPERUSER:
        desired_role = UserRole.EDITOR if can_edit else UserRole.VIEWER
        if desired_role != updated_user.role:
            next_user = repository.update_user_role(
                connection,
                user_id=updated_user.id,
                role=desired_role,
            )
            if next_user is not None:
                change_lines.append(
                    f"role: {updated_user.role.value} -> {next_user.role.value}"
                )
                updated_user = next_user

    if updated_user.is_active != is_active:
        next_user = repository.set_user_active(
            connection,
            user_id=updated_user.id,
            is_active=is_active,
        )
        if next_user is not None:
            change_lines.append(
                f"is_active: {int(updated_user.is_active)} -> {int(next_user.is_active)}"
            )
            updated_user = next_user

    if password:
        next_user = repository.update_user_password(
            connection,
            user_id=updated_user.id,
            hashed_password=auth.hash_password(password),
        )
        if next_user is not None:
            change_lines.append("password: rotated")
            updated_user = next_user

    if change_lines:
        _audit_user_change(
            connection,
            actor,
            updated_user,
            action="UPDATE",
            changes="; ".join(change_lines),
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

    errors: list[str] = []
    if confirm_username != target.username:
        errors.append("Username confirmation does not match.")
    allowed, message = _can_delete_user(connection, actor, target)
    if not allowed:
        errors.append(message)

    if errors:
        return _render_template(
            request,
            "users.html",
            _users_template_context(
                connection,
                delete_errors=errors,
                delete_form={
                    "id": str(target.id),
                    "username": target.username,
                    "confirm_username": confirm_username,
                },
            ),
            active_nav="users",
            status_code=400,
        )

    _audit_user_change(
        connection,
        actor,
        target,
        action="DELETE",
        changes=f"Deleted user (role={target.role.value}, is_active={int(target.is_active)})",
    )
    repository.delete_user(connection, target.id)

    return _redirect_with_flash(
        request,
        "/ui/users",
        "User deleted.",
        message_type="success",
        status_code=303,
    )
