from __future__ import annotations

from pathlib import Path


def test_sidebar_groups_navigation_and_exposes_semantic_labels(client) -> None:
    response = client.get("/ui/management")

    assert response.status_code == 200
    assert '<aside class="sidebar" aria-label="Primary navigation">' in response.text
    assert response.text.index("Workspace") < response.text.index("Catalog")
    assert response.text.index("Catalog") < response.text.index("Operations")
    assert 'class="nav-icon" aria-hidden="true"' not in response.text
    assert '<p class="sidebar-section-title">Administration</p>' not in response.text


def test_sidebar_keeps_active_state_on_current_page(client) -> None:
    response = client.get("/ui/management")

    assert 'class="nav-link nav-link-active" href="/ui/management"' in response.text
    assert 'class="nav-link nav-link-active" href="/ui/ip-assets"' not in response.text


def test_sidebar_uses_a_non_scrolling_light_surface() -> None:
    css = Path("app/static/css/foundation.css").read_text(encoding="utf-8")

    sidebar_rules = css.split(".sidebar-brand", maxsplit=1)[0]
    assert "background: #edf3f8;" in sidebar_rules
    assert "overflow: hidden;" in sidebar_rules
    assert "overflow-y: auto;" not in sidebar_rules


def test_sidebar_account_actions_are_compact_text_links(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.ui._is_authenticated_request", lambda request: True)
    response = client.get("/ui/management")

    assert 'class="sidebar-account-link sidebar-password-link"' in response.text
    assert (
        'class="sidebar-account-link sidebar-logout-button sidebar-account-danger"'
        in response.text
    )
    assert "sidebar-account-heading" not in response.text
