from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from app import auth
from app import repository
from app.main import app
from app.models import IPAsset, IPAssetType, User, UserRole
from app.routes.ui import utils as ui_utils
from app.routes.ui._utils import session as ui_session_utils


@dataclass
class _Obj:
    name: str | None = None
    cidr: str | None = None


def _request(path: str = "/ui/test", query: str = "", cookie: str = "") -> Request:
    headers = []
    if cookie:
        headers.append((b"cookie", cookie.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": query.encode("utf-8"),
        "headers": headers,
        "app": app,
    }
    return Request(scope)


def test_render_template_fallback_covers_payload_branches(monkeypatch) -> None:
    from app.routes import ui as ui_module

    monkeypatch.setattr(ui_module, "_is_authenticated_request", lambda _req: True)
    monkeypatch.setattr(
        ui_utils.build_info,
        "get_display_build_info",
        lambda: {"version": "1.2.3", "commit": "abc1234", "build_time": "now"},
    )
    monkeypatch.setattr(app.state, "templates", None, raising=False)

    request = _request()
    response = ui_utils._render_template(
        request,
        "management.html",
        {
            "title": "Demo",
            "assets": [{"ip_address": "10.0.0.1", "project_unassigned": True}],
            "projects": [_Obj(name="Core")],
            "hosts": [_Obj(name="edge-01"), {"name": "edge-02"}],
            "vendors": [_Obj(name="Dell"), {"name": "HP"}],
            "summary": {
                "active_ip_total": 1,
                "archived_ip_total": 2,
                "host_total": 3,
                "vendor_total": 4,
                "project_total": 5,
            },
            "utilization": [{"used": 7}],
            "errors": ["boom"],
        },
    )

    assert response.status_code == 200
    body = response.body.decode("utf-8")
    assert "Demo" in body
    assert "10.0.0.1" in body
    assert "Unassigned" in body
    assert "Core" in body
    assert "edge-01" in body
    assert "edge-02" in body
    assert "Dell" in body
    assert "HP" in body
    assert "7" in body
    assert "boom" in body
    assert "ipocket 1.2.3 (abc1234)" in body

    ranges_response = ui_utils._render_template(
        request,
        "ranges.html",
        {"ranges": [_Obj(cidr="10.20.0.0/24")]},
    )
    assert "10.20.0.0/24" in ranges_response.body.decode("utf-8")

    login_response = ui_utils._render_template(request, "login.html", {})
    assert "Login" in login_response.body.decode("utf-8")

    direct_fallback = ui_utils._render_fallback_template(
        "x.html", {"use_local_assets": True}
    )
    assert "/static/vendor/htmx.min.js" in direct_fallback.body.decode("utf-8")
    assert "cdn.jsdelivr.net/npm/alpinejs" not in direct_fallback.body.decode("utf-8")

    remote_fallback = ui_utils._render_fallback_template(
        "x.html", {"use_local_assets": False}
    )
    assert "unpkg.com/htmx.org" in remote_fallback.body.decode("utf-8")
    assert "cdn.jsdelivr.net/npm/alpinejs" in remote_fallback.body.decode("utf-8")


def test_render_template_with_templates_deletes_flash_cookie(monkeypatch) -> None:
    from app.routes import ui as ui_module

    class _Templates:
        def TemplateResponse(self, _request, _template_name, _payload, status_code=200):
            return HTMLResponse("ok", status_code=status_code)

    monkeypatch.setattr(ui_module, "_is_authenticated_request", lambda _req: False)
    monkeypatch.setattr(
        ui_utils,
        "_load_flash_messages",
        lambda _req: [{"type": "info", "message": "x"}],
    )
    monkeypatch.setattr(app.state, "templates", _Templates(), raising=False)

    request = _request()
    response = ui_utils._render_template(request, "x.html", {})

    assert response.status_code == 200
    assert ui_utils.FLASH_COOKIE in response.headers.get("set-cookie", "")


def test_flash_helpers_and_cookie_roundtrip() -> None:
    assert ui_utils._normalize_flash_type(None) == "info"
    assert ui_utils._normalize_flash_type("  BAD  ") == "info"

    bad_b64 = ui_utils._decode_flash_payload(
        base64.urlsafe_b64encode(b"\xff").decode("utf-8")
    )
    assert bad_b64 is None

    encoded = ui_utils._encode_flash_payload(
        [
            {"type": "success", "message": "ok"},
            {"type": "warn", "message": "converted"},
            "not-dict",  # type: ignore[list-item]
            {"type": "info", "message": "   "},
        ]
    )
    signed = ui_utils._sign_session_value(encoded)
    request = _request(cookie=f"{ui_utils.FLASH_COOKIE}={signed}")
    messages = ui_utils._load_flash_messages(request)
    assert messages == [
        {"type": "success", "message": "ok"},
        {"type": "info", "message": "converted"},
    ]

    assert ui_utils._verify_session_value("nosig") is None
    assert ui_utils._verify_session_value(f"{encoded}.bad") is None

    bad_decode = ui_utils._sign_session_value("a")
    bad_decode_request = _request(cookie=f"{ui_utils.FLASH_COOKIE}={bad_decode}")
    assert ui_utils._load_flash_messages(bad_decode_request) == []

    non_json_text = base64.urlsafe_b64encode(b"not-json").decode("utf-8")
    bad_json = ui_utils._sign_session_value(non_json_text)
    bad_json_request = _request(cookie=f"{ui_utils.FLASH_COOKIE}={bad_json}")
    assert ui_utils._load_flash_messages(bad_json_request) == []

    non_list_json = base64.urlsafe_b64encode(
        json.dumps({"message": "x"}).encode("utf-8")
    ).decode("utf-8")
    not_list_payload = ui_utils._sign_session_value(non_list_json)
    request2 = _request(cookie=f"{ui_utils.FLASH_COOKIE}={not_list_payload}")
    assert ui_utils._load_flash_messages(request2) == []

    response = Response()
    ui_utils._store_flash_messages(response, [])
    assert response.headers.get("set-cookie") is None


def test_get_session_secret_uses_configured_env_value(monkeypatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "configured-secret")
    monkeypatch.setattr(ui_session_utils, "_is_testing_environment", lambda: False)

    assert ui_session_utils._get_session_secret() == b"configured-secret"


def test_get_session_secret_requires_env_outside_testing(monkeypatch) -> None:
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setattr(ui_session_utils, "_is_testing_environment", lambda: False)

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        ui_session_utils._get_session_secret()

    monkeypatch.setenv("SESSION_SECRET", "   ")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        ui_session_utils._get_session_secret()


def test_get_session_secret_allows_testing_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setattr(ui_session_utils, "_is_testing_environment", lambda: True)

    assert ui_session_utils._get_session_secret() == b"test-session-secret"


def test_flash_helpers_truncate_long_messages_for_cookie_safety() -> None:
    long_message = "x" * 10000
    encoded = ui_utils._encode_flash_payload(
        [{"type": "error", "message": long_message}]
    )
    decoded = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode())
    assert len(decoded[0]["message"]) == ui_session_utils.FLASH_MAX_MESSAGE_LENGTH

    response = Response()
    ui_utils._store_flash_messages(
        response, [{"type": "error", "message": long_message}]
    )
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert len(set_cookie) < 4096


def test_get_current_user_and_editor_guard_paths(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        user = repository.create_user(
            connection, username="viewer", hashed_password="x", role=UserRole.VIEWER
        )
        signed_missing = ui_utils._sign_session_value("missing-token")
        existing_token = auth.create_access_token(connection, user.id)
        signed_existing = ui_utils._sign_session_value(existing_token)

        no_cookie_req = _request(path="/ui/hosts", query="page=2")
        with pytest.raises(HTTPException) as no_cookie_exc:
            ui_utils.get_current_ui_user(no_cookie_req, connection)
        assert no_cookie_exc.value.status_code == 303
        assert no_cookie_exc.value.headers["Location"].endswith(
            "/ui/login?return_to=/ui/hosts?page=2"
        )

        missing_user_req = _request(
            path="/ui/ip-assets",
            query="q=abc",
            cookie=f"{ui_utils.SESSION_COOKIE}={signed_missing}",
        )
        with pytest.raises(HTTPException) as missing_user_exc:
            ui_utils.get_current_ui_user(missing_user_req, connection)
        assert missing_user_exc.value.status_code == 303
        assert missing_user_exc.value.headers["Location"].endswith(
            "/ui/login?return_to=/ui/ip-assets?q=abc"
        )

        current = ui_utils.get_current_ui_user(
            _request(cookie=f"{ui_utils.SESSION_COOKIE}={signed_existing}"), connection
        )
        assert current.username == "viewer"

        with pytest.raises(HTTPException) as guard_exc:
            ui_utils.require_ui_editor(current)
        assert guard_exc.value.status_code == 403

        editor = User(2, "editor", "x", UserRole.EDITOR, True)
        assert ui_utils.require_ui_editor(editor) == editor
    finally:
        connection.close()


def test_parsers_and_inline_ip_collection_helpers(_setup_connection) -> None:
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, name="edge-01")
        repository.create_ip_asset(
            connection,
            ip_address="10.99.0.1",
            asset_type=IPAssetType.OS,
            host_id=host.id,
        )

        assert ui_utils._parse_optional_int_query("abc") is None
        assert ui_utils._parse_positive_int_query("-1", 20) == 20

        parsed_ips = ui_utils._parse_inline_ip_list("10.0.0.1, 10.0.0.1  10.0.0.2")
        assert parsed_ips == ["10.0.0.1", "10.0.0.2"]

        errors, to_create, to_update = ui_utils._collect_inline_ip_errors(
            connection,
            host.id,
            ["bad-ip", "10.1.1.1", "10.99.0.1"],
            ["10.1.1.1", "10.99.0.2"],
        )
        assert "IP address appears in both OS and BMC fields: 10.1.1.1." in errors
        assert "Invalid IP address. (bad-ip)" in errors
        assert ("10.99.0.2", IPAssetType.BMC) in to_create
        assert to_update == []

        errors2, to_create2, to_update2 = ui_utils._collect_inline_ip_errors(
            connection,
            host.id,
            ["10.99.0.3"],
            [],
        )
        assert errors2 == []
        assert to_create2 == [("10.99.0.3", IPAssetType.OS)]
        assert to_update2 == []
    finally:
        connection.close()


def test_export_type_csv_json_zip_and_view_models_helpers() -> None:
    with pytest.raises(HTTPException) as exc:
        ui_utils._normalize_export_asset_type("BAD")
    assert exc.value.status_code == 422

    csv_content = ui_utils._build_csv_content(["a", "b"], [{"a": 1, "b": None}])
    assert "a,b" in csv_content
    assert "1," in csv_content

    csv_response = ui_utils._csv_response("x.csv", ["a"], [{"a": "1"}])
    assert csv_response.headers["Content-Disposition"] == 'attachment; filename="x.csv"'

    json_response = ui_utils._json_response("x.json", {"ok": True})
    assert (
        json_response.headers["Content-Disposition"] == 'attachment; filename="x.json"'
    )

    zip_response = ui_utils._zip_response("x.zip", {"one.txt": "1"})
    assert zip_response.headers["Content-Disposition"] == 'attachment; filename="x.zip"'
    assert zip_response.media_type == "application/zip"

    asset = IPAsset(
        id=1,
        ip_address="10.10.0.1",
        asset_type=IPAssetType.OS,
        project_id=1,
        host_id=1,
        notes=None,
        archived=False,
        created_at="",
        updated_at="",
    )
    models = ui_utils._build_asset_view_models(
        [asset],
        {1: {"name": "Core", "color": "#123456"}},
        {1: "edge-01"},
        {1: [{"name": "prod", "color": "#fff"}]},
        {1: {IPAssetType.BMC.value: ["10.10.0.2"]}},
    )
    assert models[0]["host_pair"] == "10.10.0.2"
    assert models[0]["project_name"] == "Core"


def test_utils_module_keeps_legacy_symbols_mapped_to_new_modules() -> None:
    assert ui_utils._sign_session_value is ui_session_utils._sign_session_value
    assert ui_utils._verify_session_value is ui_session_utils._verify_session_value
    assert ui_utils.get_current_ui_user is ui_session_utils.get_current_ui_user
