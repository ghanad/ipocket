from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app import auth, repository
from app.dependencies import get_connection
from .utils import (
    _parse_form_data,
    _redirect_with_flash,
    _render_template,
    get_current_ui_user,
)

router = APIRouter()


def _account_password_context(
    *,
    errors: list[str] | None = None,
) -> dict:
    return {
        "title": "ipocket - Change Password",
        "errors": errors or [],
    }


@router.get("/ui/account/password", response_class=HTMLResponse)
def ui_account_password_form(
    request: Request,
    _user=Depends(get_current_ui_user),
) -> HTMLResponse:
    return _render_template(
        request,
        "account_password.html",
        _account_password_context(),
        active_nav="",
    )


@router.post("/ui/account/password", response_class=HTMLResponse)
async def ui_account_password_submit(
    request: Request,
    connection=Depends(get_connection),
    user=Depends(get_current_ui_user),
) -> Response:
    form_data = await _parse_form_data(request)
    current_password = form_data.get("current_password") or ""
    new_password = form_data.get("new_password") or ""
    confirm_new_password = form_data.get("confirm_new_password") or ""

    errors: list[str] = []
    if not current_password:
        errors.append("Current password is required.")
    if not new_password:
        errors.append("New password is required.")
    if not confirm_new_password:
        errors.append("Confirm new password is required.")
    if new_password and confirm_new_password and new_password != confirm_new_password:
        errors.append("New password and confirmation do not match.")
    if current_password and new_password and current_password == new_password:
        errors.append("New password must be different from current password.")
    if current_password and not auth.verify_password(
        current_password, user.hashed_password
    ):
        errors.append("Current password is incorrect.")

    if errors:
        return _render_template(
            request,
            "account_password.html",
            _account_password_context(errors=errors),
            active_nav="",
            status_code=400,
        )

    updated_user = repository.update_user_password(
        connection,
        user_id=user.id,
        hashed_password=auth.hash_password(new_password),
    )
    if updated_user is None:
        return Response(status_code=404)

    repository.create_audit_log(
        connection,
        user=updated_user,
        action="UPDATE",
        target_type="USER",
        target_id=updated_user.id,
        target_label=updated_user.username,
        changes="password: self-service rotated",
    )
    connection.commit()

    return _redirect_with_flash(
        request,
        "/ui/account/password",
        "Password changed successfully.",
        message_type="success",
        status_code=303,
    )
