from __future__ import annotations

from app import repository as repository_module
from app.routes.ui import ip_assets, ranges, settings


def test_ip_assets_module_reexports_helper_functions() -> None:
    assert callable(ip_assets._friendly_audit_changes)
    assert callable(ip_assets._parse_selected_tags)
    assert callable(ip_assets._delete_requires_exact_ip)


def test_ranges_module_reexports_repository_and_tag_parser() -> None:
    assert ranges.repository is repository_module
    assert callable(ranges._parse_selected_tags)


def test_settings_module_reexports_repository_and_tag_color_provider(
    _setup_connection, monkeypatch
) -> None:
    assert settings.repository is repository_module

    monkeypatch.setattr(settings, "suggest_random_tag_color", lambda: "#123abc")
    connection = _setup_connection()
    try:
        context = settings._tags_template_context(connection)
    finally:
        connection.close()

    assert context["form_state"]["color"] == "#123abc"
