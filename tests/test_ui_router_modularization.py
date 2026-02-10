from app.routes import ui


def test_ui_router_includes_modular_route_groups() -> None:
    paths = {route.path for route in ui.router.routes}
    assert "/ui/login" in paths
    assert "/ui/management" in paths
    assert "/ui/ip-assets" in paths
    assert "/ui/hosts" in paths
    assert "/ui/ranges" in paths
    assert "/ui/projects" in paths
    assert "/ui/import" in paths


def test_ui_module_keeps_legacy_testing_exports() -> None:
    assert callable(ui.require_ui_editor)
    assert callable(ui.get_current_ui_user)
    assert callable(ui._encode_flash_payload)
    assert callable(ui._sign_session_value)
    assert isinstance(ui.FLASH_COOKIE, str)
    assert isinstance(ui.SESSION_COOKIE, str)
