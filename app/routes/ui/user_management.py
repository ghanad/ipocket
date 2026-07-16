from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app import auth, repository
from app.models import User, UserRole


@dataclass(frozen=True)
class UserMutationError(Exception):
    status_code: int
    message: str


@dataclass(frozen=True)
class UserUpdateResult:
    user: User
    changed: bool


def can_deactivate_superuser(connection, user: User) -> bool:
    if user.role != UserRole.SUPERUSER:
        return True
    active_superusers = repository.count_active_users_by_role(
        connection, UserRole.SUPERUSER
    )
    return active_superusers > 1


def delete_policy(connection, actor: User, target: User) -> tuple[bool, str]:
    if target.id == actor.id:
        return False, "You cannot delete your own account."
    if target.role == UserRole.SUPERUSER and not can_deactivate_superuser(
        connection, target
    ):
        return False, "Cannot delete the last active superuser."
    return True, ""


def user_payload(connection, actor: User, user: User) -> dict[str, object]:
    can_delete, delete_reason = delete_policy(connection, actor, user)
    can_deactivate = can_deactivate_superuser(connection, user)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "role_label": (
            "Superuser" if user.role == UserRole.SUPERUSER else user.role.value
        ),
        "is_active": user.is_active,
        "policy": {
            "can_edit_role": user.role != UserRole.SUPERUSER,
            "can_deactivate": can_deactivate,
            "can_delete": can_delete,
            "delete_disabled_reason": delete_reason or None,
        },
    }


def _audit_user_change(
    connection, actor: User, target: User, action: str, changes: str
) -> None:
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


def create_managed_user(
    connection,
    actor: User,
    *,
    username: str,
    password: str,
    can_edit: bool,
    is_active: bool,
) -> User:
    normalized_username = username.strip()
    if not normalized_username:
        raise UserMutationError(422, "Username is required.")
    if not password:
        raise UserMutationError(422, "Password is required.")

    role = UserRole.EDITOR if can_edit else UserRole.VIEWER
    try:
        created = repository.create_user(
            connection,
            username=normalized_username,
            hashed_password=auth.hash_password(password),
            role=role,
            is_active=is_active,
        )
    except sqlite3.IntegrityError as exc:
        raise UserMutationError(409, "Username already exists.") from exc

    _audit_user_change(
        connection,
        actor,
        created,
        action="CREATE",
        changes=(
            f"Created user (role={created.role.value}, "
            f"is_active={int(created.is_active)})"
        ),
    )
    return created


def update_managed_user(
    connection,
    actor: User,
    target: User,
    *,
    can_edit: bool,
    is_active: bool,
    password: str,
) -> UserUpdateResult:
    if target.role == UserRole.SUPERUSER and not can_edit:
        raise UserMutationError(403, "Superuser edit access cannot be changed.")
    if not is_active and not can_deactivate_superuser(connection, target):
        raise UserMutationError(403, "Cannot deactivate the last active superuser.")

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
                f"is_active: {int(updated_user.is_active)} -> "
                f"{int(next_user.is_active)}"
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

    return UserUpdateResult(user=updated_user, changed=bool(change_lines))


def delete_managed_user(
    connection,
    actor: User,
    target: User,
    *,
    confirm_username: str,
) -> None:
    if confirm_username.strip() != target.username:
        raise UserMutationError(422, "Username confirmation does not match.")

    allowed, message = delete_policy(connection, actor, target)
    if not allowed:
        raise UserMutationError(403, message)

    _audit_user_change(
        connection,
        actor,
        target,
        action="DELETE",
        changes=(
            f"Deleted user (role={target.role.value}, "
            f"is_active={int(target.is_active)})"
        ),
    )
    repository.delete_user(connection, target.id)
