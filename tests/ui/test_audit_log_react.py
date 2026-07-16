from __future__ import annotations

import pytest

from app import repository
from app.main import app
from app.models import User, UserRole
from app.routes import ui


def _user(role: UserRole = UserRole.VIEWER) -> User:
    return User(1, role.value.lower(), "x", role, True)


def _override_user(role: UserRole = UserRole.VIEWER) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: _user(role)


def _clear_user_override() -> None:
    app.dependency_overrides.pop(ui.get_current_ui_user, None)


def _create_logs(connection, count: int, *, user=None) -> None:
    for index in range(count):
        repository.create_audit_log(
            connection,
            user=user,
            action="CREATE" if index % 2 == 0 else "UPDATE",
            target_type="IP_ASSET" if index % 3 else "IMPORT_RUN",
            target_id=index + 1,
            target_label=f"target-{index + 1}",
            changes=f"change-{index + 1}",
        )
    connection.commit()


def test_audit_log_page_is_authenticated_lightweight_react_mount(client) -> None:
    _override_user()
    try:
        response = client.get("/ui/audit-log?page=2&per-page=10")
    finally:
        _clear_user_override()

    assert response.status_code == 200
    assert "<title>ipocket - Audit Log</title>" in response.text
    assert 'id="audit-log-root"' in response.text
    assert 'data-endpoint="/api/ui/audit-log"' in response.text
    assert 'data-initial-query="page=2&amp;per-page=10"' in response.text
    assert (
        '<script type="module" src="/static/react/audit-log/audit-log.js"></script>'
        in response.text
    )
    assert "<table" not in response.text
    assert "target-" not in response.text


@pytest.mark.parametrize(
    "role",
    [UserRole.VIEWER, UserRole.EDITOR, UserRole.SUPERUSER],
)
def test_audit_log_page_and_api_allow_all_authenticated_ui_roles(
    client, role: UserRole
) -> None:
    _override_user(role)
    try:
        page = client.get("/ui/audit-log")
        api = client.get("/api/ui/audit-log")
    finally:
        _clear_user_override()

    assert page.status_code == 200
    assert api.status_code == 200


def test_audit_log_api_requires_authentication(client) -> None:
    response = client.get("/api/ui/audit-log", follow_redirects=False)

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/ui/login?return_to=/api/ui/audit-log"
    )


def test_audit_log_api_shape_ordering_and_system_fallback(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        actor = repository.create_user(
            connection,
            username="auditor",
            hashed_password="x",
            role=UserRole.EDITOR,
        )
        repository.create_audit_log(
            connection,
            user=actor,
            action="APPLY",
            target_type="IMPORT_RUN",
            target_id=1,
            target_label="bundle-import",
            changes="created=1",
        )
        repository.create_audit_log(
            connection,
            user=None,
            action="DELETE",
            target_type="USER",
            target_id=2,
            target_label="retired-user",
            changes=None,
        )
        connection.commit()
    finally:
        connection.close()

    _override_user()
    try:
        response = client.get("/api/ui/audit-log")
    finally:
        _clear_user_override()

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"audit_logs", "pagination", "query"}
    assert payload["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 2,
        "total_pages": 1,
    }
    assert payload["query"] == {"page": 1, "per_page": 20}
    assert [row["target_label"] for row in payload["audit_logs"]] == [
        "retired-user",
        "bundle-import",
    ]
    assert payload["audit_logs"][0] == {
        "id": payload["audit_logs"][0]["id"],
        "created_at": payload["audit_logs"][0]["created_at"],
        "target_label": "retired-user",
        "username": "System",
        "action": "DELETE",
        "changes": "",
    }
    assert payload["audit_logs"][1]["username"] == "auditor"


def test_audit_log_api_default_and_custom_pagination(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        _create_logs(connection, 25)
    finally:
        connection.close()

    _override_user()
    try:
        default = client.get("/api/ui/audit-log").json()
        custom = client.get(
            "/api/ui/audit-log?page=2&per-page=10"
        ).json()
    finally:
        _clear_user_override()

    assert default["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 25,
        "total_pages": 2,
    }
    assert len(default["audit_logs"]) == 20
    assert default["audit_logs"][0]["target_label"] == "target-25"
    assert custom["pagination"] == {
        "page": 2,
        "per_page": 10,
        "total": 25,
        "total_pages": 3,
    }
    assert len(custom["audit_logs"]) == 10
    assert custom["audit_logs"][0]["target_label"] == "target-15"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("page=invalid&per-page=15", {"page": 1, "per_page": 20}),
        ("page=0&per-page=-10", {"page": 1, "per_page": 20}),
        ("page=999&per-page=10", {"page": 3, "per_page": 10}),
    ],
)
def test_audit_log_api_normalizes_invalid_values_and_clamps_final_page(
    client, _setup_connection, query: str, expected: dict[str, int]
) -> None:
    connection = _setup_connection()
    try:
        _create_logs(connection, 25)
    finally:
        connection.close()

    _override_user()
    try:
        payload = client.get(f"/api/ui/audit-log?{query}").json()
    finally:
        _clear_user_override()

    assert payload["query"] == expected
    assert payload["pagination"]["page"] == expected["page"]
    assert payload["pagination"]["per_page"] == expected["per_page"]


def test_audit_log_api_empty_history(client, _setup_connection) -> None:
    connection = _setup_connection()
    connection.close()

    _override_user()
    try:
        payload = client.get("/api/ui/audit-log").json()
    finally:
        _clear_user_override()

    assert payload["audit_logs"] == []
    assert payload["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 0,
        "total_pages": 1,
    }


def test_audit_log_api_keeps_repository_pagination_compatibility(
    client, _setup_connection
) -> None:
    connection = _setup_connection()
    try:
        _create_logs(connection, 14)
        repository_rows = repository.list_audit_logs_paginated(
            connection,
            target_type=None,
            limit=10,
            offset=10,
        )
        repository_total = repository.count_audit_logs(
            connection, target_type=None
        )
    finally:
        connection.close()

    _override_user()
    try:
        payload = client.get(
            "/api/ui/audit-log?page=2&per-page=10"
        ).json()
    finally:
        _clear_user_override()

    assert payload["pagination"]["total"] == repository_total
    assert [row["id"] for row in payload["audit_logs"]] == [
        row.id for row in repository_rows
    ]
