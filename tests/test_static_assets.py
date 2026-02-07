from pathlib import Path


def test_ui_assets_are_local() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base_html = (repo_root / "app/templates/base.html").read_text(encoding="utf-8")
    assert "/static/vendor/htmx.min.js" in base_html
    assert "unpkg.com" not in base_html

    css = (repo_root / "app/static/app.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in css
    assert "font-family: \"Inter\"" in css
