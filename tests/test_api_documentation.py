from app.main import app
from app.models import User, UserRole
from app.routes import ui


def test_api_ui_about_includes_documentation_links(client) -> None:
    app.dependency_overrides[ui.get_current_ui_user] = lambda: User(
        1, "docs-viewer", "unused", UserRole.VIEWER, True
    )
    try:
        response = client.get("/api/ui/about")
        assert response.status_code == 200
        data = response.json()
        assert "links" in data
        assert data["links"]["docs"] == "/docs"
        assert data["links"]["redoc"] == "/redoc"
        assert data["links"]["health"] == "/health"
        assert data["links"]["metrics"] == "/metrics"
    finally:
        app.dependency_overrides.pop(ui.get_current_ui_user, None)


def test_openapi_schema_documents_ip_assets_filtering(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    # Verify /ip-assets
    assert "/ip-assets" in paths
    ip_assets_get = paths["/ip-assets"]["get"]
    assert "active IP assets" in ip_assets_get["description"]
    type_param = next(p for p in ip_assets_get["parameters"] if p["name"] == "type")
    assert "BMC" in type_param["description"]

    # Verify /api/ui/ip-assets
    assert "/api/ui/ip-assets" in paths
    ui_ip_assets_get = paths["/api/ui/ip-assets"]["get"]
    ui_type_param = next(
        p for p in ui_ip_assets_get["parameters"] if p["name"] == "type"
    )
    assert "BMC" in ui_type_param["description"]


def test_swagger_and_redoc_endpoints_accessible(client) -> None:
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200
    assert "swagger" in docs_resp.text.lower() or "html" in docs_resp.text.lower()

    redoc_resp = client.get("/redoc")
    assert redoc_resp.status_code == 200
    assert "redoc" in redoc_resp.text.lower() or "html" in redoc_resp.text.lower()
