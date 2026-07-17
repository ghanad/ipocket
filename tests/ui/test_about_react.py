from __future__ import annotations

from contextlib import contextmanager

from app import build_info
from app.main import app
from app.models import User, UserRole
from app.routes import ui


@contextmanager
def _authenticated_about_user():
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "about-viewer", "unused", UserRole.VIEWER, True
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_about_page_requires_authentication(client) -> None:
    response = client.get("/ui/about", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/ui/about"


def test_about_page_is_a_lightweight_react_mount(client, monkeypatch) -> None:
    monkeypatch.setattr(
        build_info,
        "get_display_build_info",
        lambda: {
            "version": "server-version-must-not-render",
            "commit": "server-commit-must-not-render",
            "build_time": "server-time-must-not-render",
        },
    )

    with _authenticated_about_user():
        response = client.get("/ui/about")

    assert response.status_code == 200
    assert 'id="about-root"' in response.text
    assert 'data-endpoint="/api/ui/about"' in response.text
    assert '<section class="card" role="status">Loading About…</section>' in response.text
    assert 'src="/static/react/about/about.js"' in response.text
    assert 'href="/ui/about"' in response.text
    assert "server-version-must-not-render" not in response.text
    assert "server-commit-must-not-render" not in response.text
    assert "server-time-must-not-render" not in response.text
    assert "Version:" not in response.text
    assert "Build time:" not in response.text


def test_about_api_requires_authentication(client) -> None:
    response = client.get("/api/ui/about", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/ui/login?return_to=/api/ui/about"


def test_about_api_returns_only_safe_structured_build_data(
    client, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_PASSWORD", "must-not-leak")
    monkeypatch.setenv("SESSION_SECRET", "also-must-not-leak")
    monkeypatch.setattr(
        build_info,
        "get_display_build_info",
        lambda: {
            "version": "2.4.1",
            "commit": "abc1234",
            "build_time": "2026-07-17T12:34:56Z",
        },
    )

    with _authenticated_about_user():
        response = client.get("/api/ui/about")

    assert response.status_code == 200
    assert response.json() == {
        "application": {"name": "ipocket"},
        "build": {
            "version": "2.4.1",
            "commit": "abc1234",
            "build_time": "2026-07-17T12:34:56Z",
        },
        "links": {"health": "/health", "metrics": "/metrics"},
    }
    assert "must-not-leak" not in response.text
    assert "DATABASE_PASSWORD" not in response.text
    assert "SESSION_SECRET" not in response.text
    assert set(response.json()) == {"application", "build", "links"}


def test_operational_endpoints_remain_public_and_unchanged(client) -> None:
    health = client.get("/health")
    metrics = client.get("/metrics")

    assert health.status_code == 200
    assert set(health.json()) == {"status", "version", "commit", "build_time"}
    assert health.json()["status"] == "ok"
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain")
    assert "ipam_ip_total " in metrics.text
    assert "ipam_ip_archived_total " in metrics.text
    assert "ipam_ip_unassigned_project_total " in metrics.text
    assert "ipam_ip_unassigned_owner_total " in metrics.text
    assert "ipam_ip_unassigned_both_total " in metrics.text
