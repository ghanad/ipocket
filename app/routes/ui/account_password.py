from __future__ import annotations

from dataclasses import dataclass

from app import auth, repository
from app.models import User


@dataclass(frozen=True)
class AccountPasswordError(Exception):
    status_code: int
    messages: tuple[str, ...]


def change_account_password(
    connection,
    user: User | None,
    *,
    current_password: str,
    new_password: str,
    confirm_new_password: str,
) -> User:
    if user is None:
        raise AccountPasswordError(404, ("Authenticated user not found.",))

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
        raise AccountPasswordError(400, tuple(errors))

    updated_user = repository.update_user_password(
        connection,
        user_id=user.id,
        hashed_password=auth.hash_password(new_password),
    )
    if updated_user is None:
        raise AccountPasswordError(404, ("Authenticated user not found.",))

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
    return updated_user
