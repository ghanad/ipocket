from pathlib import Path

from app.environment import use_local_assets


def test_ui_assets_are_local() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base_html = (repo_root / "app/templates/base.html").read_text(encoding="utf-8")
    assert "/static/vendor/htmx.min.js" in base_html
    assert "unpkg.com/htmx.org" in base_html
    assert "{% if not use_local_assets %}" in base_html
    assert "fonts.googleapis.com" in base_html

    css = (repo_root / "app/static/app.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in css
    assert "font-family: \"Inter\"" in css
    assert "height: 100vh" in css
    assert "position: sticky" in css
    assert "overflow-y: auto" in css


def test_use_local_assets_env_override(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_DOCKER_ASSETS", "1")
    assert use_local_assets() is True

    monkeypatch.setenv("IPOCKET_DOCKER_ASSETS", "0")
    assert use_local_assets() is False


def test_refactored_templates_load_external_page_assets() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    templates = {
        "hosts": repo_root / "app/templates/hosts.html",
        "ip_assets": repo_root / "app/templates/ip_assets_list.html",
        "range_addresses": repo_root / "app/templates/range_addresses.html",
        "tags": repo_root / "app/templates/tags.html",
        "audit_log": repo_root / "app/templates/audit_log_list.html",
    }

    assert '<script src="/static/js/hosts.js" defer></script>' in templates["hosts"].read_text(encoding="utf-8")
    assert "<style>" not in templates["hosts"].read_text(encoding="utf-8")
    assert "<script>" not in templates["hosts"].read_text(encoding="utf-8")

    assert '<script src="/static/js/ip-assets.js" defer></script>' in templates["ip_assets"].read_text(encoding="utf-8")
    assert "<style>" not in templates["ip_assets"].read_text(encoding="utf-8")
    assert "<script>" not in templates["ip_assets"].read_text(encoding="utf-8")

    assert '<script src="/static/js/range-addresses.js" defer></script>' in templates["range_addresses"].read_text(encoding="utf-8")
    assert "<style>" not in templates["range_addresses"].read_text(encoding="utf-8")

    assert '<script src="/static/js/tags.js" defer></script>' in templates["tags"].read_text(encoding="utf-8")
    assert "<script>" not in templates["tags"].read_text(encoding="utf-8")

    assert "<style>" not in templates["audit_log"].read_text(encoding="utf-8")

    assert (repo_root / "app/static/js/hosts.js").exists()
    assert (repo_root / "app/static/js/ip-assets.js").exists()
    assert (repo_root / "app/static/js/range-addresses.js").exists()
    assert (repo_root / "app/static/js/tags.js").exists()
