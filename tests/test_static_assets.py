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


def test_use_local_assets_env_override(monkeypatch) -> None:
    monkeypatch.setenv("IPOCKET_DOCKER_ASSETS", "1")
    assert use_local_assets() is True

    monkeypatch.setenv("IPOCKET_DOCKER_ASSETS", "0")
    assert use_local_assets() is False
