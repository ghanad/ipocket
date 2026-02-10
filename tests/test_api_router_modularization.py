from app.routes import api


def test_api_router_includes_modular_route_groups() -> None:
    paths = {route.path for route in api.router.routes}
    assert "/health" in paths
    assert "/metrics" in paths
    assert "/login" in paths
    assert "/ip-assets" in paths
    assert "/hosts" in paths
    assert "/projects" in paths
    assert "/vendors" in paths
    assert "/ranges" in paths
    assert "/import/bundle" in paths
    assert "/import/csv" in paths


def test_api_module_keeps_legacy_dependency_exports() -> None:
    assert callable(api.require_editor)
    assert callable(api.get_current_user)
