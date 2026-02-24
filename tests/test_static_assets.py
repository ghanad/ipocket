from pathlib import Path

from app.environment import use_local_assets


def test_ui_assets_are_local() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base_html = (repo_root / "app/templates/base.html").read_text(encoding="utf-8")
    assert "/static/vendor/htmx.min.js" in base_html
    assert "unpkg.com/htmx.org" in base_html
    assert "{% if not use_local_assets %}" in base_html
    assert "fonts.googleapis.com" in base_html
    assert "cdn.jsdelivr.net/npm/alpinejs" in base_html
    assert '<script src="/static/js/tag-picker.js" defer></script>' in base_html

    css = (repo_root / "app/static/app.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in css
    assert 'font-family: "Inter"' in css
    assert "height: 100vh" in css
    assert "position: sticky" in css
    assert "overflow-y: auto" in css
    assert ".field > span {" in css
    assert ".table.table-ip-assets .tag {" in css
    assert "padding: 3px 9px;" in css
    assert ".table.table-range-addresses .tag {" in css
    assert ".ip-tags-popover {" in css
    assert "z-index: 120;" in css
    assert ".ip-tags-popover .tag {" in css
    assert "font-size: 12px;" in css
    assert ".ip-tags-inline > .tag-filter-chip {" in css
    assert "max-width: 72px;" in css
    assert ".ip-tags-inline > .ip-tags-more {" in css
    assert "flex-shrink: 0;" in css
    assert "color: var(--tag-color-text, #0f172a);" in css
    assert ".tag-picker-dropdown[hidden] {" in css
    assert "display: none;" in css
    assert ".bulk-edit-controls {" in css
    assert "background: #f8fafc;" in css
    assert ".bulk-drawer-selection {" in css
    assert ".bulk-common-tags {" in css
    assert ".bulk-common-tag-chip.is-marked {" in css


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
        "ip_assets_table": repo_root / "app/templates/partials/ip_assets_table.html",
        "ip_assets_rows": repo_root / "app/templates/partials/ip_table_rows.html",
        "range_addresses": repo_root / "app/templates/range_addresses.html",
        "tags": repo_root / "app/templates/tags.html",
        "audit_log": repo_root / "app/templates/audit_log_list.html",
    }

    assert '<script src="/static/js/drawer.js" defer></script>' in templates[
        "hosts"
    ].read_text(encoding="utf-8")
    assert '<script src="/static/js/hosts.js" defer></script>' in templates[
        "hosts"
    ].read_text(encoding="utf-8")
    assert "<style>" not in templates["hosts"].read_text(encoding="utf-8")
    assert "<script>" not in templates["hosts"].read_text(encoding="utf-8")

    assert '<script src="/static/js/ip-assets.js" defer></script>' in templates[
        "ip_assets"
    ].read_text(encoding="utf-8")
    assert "data-bulk-open disabled>Bulk update</button>" in templates[
        "ip_assets_table"
    ].read_text(encoding="utf-8")
    assert "data-bulk-remove-hidden" in templates["ip_assets_table"].read_text(
        encoding="utf-8"
    )
    assert "data-bulk-drawer" in templates["ip_assets"].read_text(encoding="utf-8")
    assert "data-bulk-common-tags-list" in templates["ip_assets"].read_text(
        encoding="utf-8"
    )
    assert 'name="notes_mode"' in templates["ip_assets"].read_text(encoding="utf-8")
    assert "data-bulk-tags=" in templates["ip_assets_rows"].read_text(encoding="utf-8")
    assert "<style>" not in templates["ip_assets"].read_text(encoding="utf-8")
    assert "<script>" not in templates["ip_assets"].read_text(encoding="utf-8")

    assert '<script src="/static/js/range-addresses.js" defer></script>' in templates[
        "range_addresses"
    ].read_text(encoding="utf-8")
    assert 'class="table table-range-addresses"' in (
        repo_root / "app/templates/partials/range_addresses_table.html"
    ).read_text(encoding="utf-8")
    assert "<style>" not in templates["range_addresses"].read_text(encoding="utf-8")

    assert '{% include "partials/tags_tab_content.html" %}' in templates[
        "tags"
    ].read_text(encoding="utf-8")
    assert "@click=\"$dispatch('tag-create-open')\"" in templates["tags"].read_text(
        encoding="utf-8"
    )
    assert "<script>" not in templates["tags"].read_text(encoding="utf-8")

    assert "<style>" not in templates["audit_log"].read_text(encoding="utf-8")

    assert (repo_root / "app/static/js/drawer.js").exists()
    assert (repo_root / "app/static/js/ranges.js").exists()
    assert (repo_root / "app/static/js/hosts.js").exists()
    assert (repo_root / "app/static/js/ip-assets.js").exists()
    assert (repo_root / "app/static/js/range-addresses.js").exists()
    assert (repo_root / "app/static/js/tag-picker.js").exists()
    tag_picker_js = (repo_root / "app/static/js/tag-picker.js").read_text(
        encoding="utf-8"
    )
    assert "picker.append(inputWrap, selectedWrap);" in tag_picker_js
    assert "const getTagTextColor = (backgroundColor) => {" in tag_picker_js
    assert (
        'element.style.setProperty("--tag-color-text", getTagTextColor(backgroundColor));'
        in tag_picker_js
    )
    assert "window.ipocketApplyTagContrast = applyTagContrast;" in tag_picker_js
    assert "applyTagContrast(root);" in tag_picker_js
    ip_assets_js = (repo_root / "app/static/js/ip-assets.js").read_text(
        encoding="utf-8"
    )
    assert "computeCommonBulkTags" in ip_assets_js
    assert "name = 'remove_tags'" in ip_assets_js


def test_projects_templates_use_alpine_for_drawer_interactions() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    projects_template = (repo_root / "app/templates/projects.html").read_text(
        encoding="utf-8"
    )
    projects_partial = (
        repo_root / "app/templates/partials/projects_tab_content.html"
    ).read_text(encoding="utf-8")

    assert "@click=\"$dispatch('project-create-open')\"" in projects_template
    assert 'x-data="' in projects_partial
    assert '@project-create-open.window="openCreate()"' in projects_partial
    assert 'x-show="createOpen"' in projects_partial
    assert 'x-show="editOpen"' in projects_partial
    assert 'x-show="deleteOpen"' in projects_partial
    assert 'x-model="createName"' in projects_partial
    assert 'x-model="editName"' in projects_partial
    assert 'x-model="deleteConfirmName"' in projects_partial
    assert "{% if use_local_assets %}" in projects_partial
    assert '<script src="/static/js/drawer.js" defer></script>' in projects_partial
    assert '<script src="/static/js/projects.js" defer></script>' in projects_partial


def test_tags_templates_use_alpine_for_drawer_interactions() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    projects_template = (repo_root / "app/templates/projects.html").read_text(
        encoding="utf-8"
    )
    tags_partial = (
        repo_root / "app/templates/partials/tags_tab_content.html"
    ).read_text(encoding="utf-8")

    assert "@click=\"$dispatch('tag-create-open')\"" in projects_template
    assert "{% import 'macros/drawer.html' as drawer_macros %}" in tags_partial
    assert 'x-data="' in tags_partial
    assert "randomHexColor()" in tags_partial
    assert '@tag-create-open.window="openCreate()"' in tags_partial
    assert 'x-show="createOpen"' in tags_partial
    assert 'x-show="editOpen"' in tags_partial
    assert 'x-show="deleteOpen"' in tags_partial
    assert 'x-model="createName"' in tags_partial
    assert 'x-model="editName"' in tags_partial
    assert 'x-model="deleteConfirmName"' in tags_partial
    assert "{% if use_local_assets %}" in tags_partial
    assert '<script src="/static/js/drawer.js" defer></script>' in tags_partial
    assert '<script src="/static/js/tags.js" defer></script>' in tags_partial
    tags_js = (repo_root / "app/static/js/tags.js").read_text(encoding="utf-8")
    assert "data-tag-add" in tags_js
    assert "data-tag-create-overlay" in tags_js
    assert "/ui/tags/" in tags_js


def test_vendors_templates_use_alpine_for_drawer_interactions() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    projects_template = (repo_root / "app/templates/projects.html").read_text(
        encoding="utf-8"
    )
    vendors_partial = (
        repo_root / "app/templates/partials/vendors_tab_content.html"
    ).read_text(encoding="utf-8")

    assert "@click=\"$dispatch('vendor-create-open')\"" in projects_template
    assert "{% import 'macros/drawer.html' as drawer_macros %}" in vendors_partial
    assert 'x-data="' in vendors_partial
    assert '@vendor-create-open.window="openCreate()"' in vendors_partial
    assert 'x-show="createOpen"' in vendors_partial
    assert 'x-show="editOpen"' in vendors_partial
    assert 'x-show="deleteOpen"' in vendors_partial
    assert 'x-model="createName"' in vendors_partial
    assert 'x-model="editName"' in vendors_partial
    assert 'x-model="deleteConfirmName"' in vendors_partial
    assert "{% if use_local_assets %}" in vendors_partial
    assert '<script src="/static/js/drawer.js" defer></script>' in vendors_partial
    assert '<script src="/static/js/vendors.js" defer></script>' in vendors_partial
    vendors_js = (repo_root / "app/static/js/vendors.js").read_text(encoding="utf-8")
    assert "data-vendor-add" in vendors_js
    assert "data-vendor-create-overlay" in vendors_js
    assert "/ui/vendors/" in vendors_js


def test_hosts_drawer_css_matches_ip_drawer_layout_baseline() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    css = (repo_root / "app/static/app.css").read_text(encoding="utf-8")

    assert ".host-drawer {" in css
    assert "width: min(480px, 100%);" in css
    assert "transform: translateX(100%);" in css
    assert ".host-drawer-form {" in css
    assert "flex-direction: column;" in css
