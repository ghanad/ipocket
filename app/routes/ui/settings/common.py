from __future__ import annotations

from typing import Optional

import app.routes.ui.settings as settings_routes

from app.utils import DEFAULT_TAG_COLOR

from . import repository


def _tags_template_context(
    connection,
    *,
    errors: Optional[list[str]] = None,
    form_state: Optional[dict[str, str]] = None,
    edit_errors: Optional[list[str]] = None,
    edit_tag=None,
    edit_form_state: Optional[dict[str, str]] = None,
    delete_errors: Optional[list[str]] = None,
    delete_tag=None,
    delete_confirm_value: str = "",
) -> dict:
    return {
        "title": "ipocket - Tags",
        "active_tab": "tags",
        "tags": list(repository.list_tags(connection)),
        "tag_ip_counts": repository.list_tag_ip_counts(connection),
        "errors": errors or [],
        "form_state": form_state
        or {"name": "", "color": settings_routes.suggest_random_tag_color()},
        "edit_errors": edit_errors or [],
        "edit_tag": edit_tag,
        "edit_form_state": edit_form_state
        or {
            "name": edit_tag.name if edit_tag else "",
            "color": edit_tag.color if edit_tag else DEFAULT_TAG_COLOR,
        },
        "delete_errors": delete_errors or [],
        "delete_tag": delete_tag,
        "delete_confirm_value": delete_confirm_value,
    }


def _vendors_template_context(
    connection,
    *,
    errors: Optional[list[str]] = None,
    form_state: Optional[dict[str, str]] = None,
    edit_errors: Optional[list[str]] = None,
    edit_vendor=None,
    edit_form_state: Optional[dict[str, str]] = None,
    delete_errors: Optional[list[str]] = None,
    delete_vendor=None,
    delete_confirm_value: str = "",
) -> dict:
    return {
        "title": "ipocket - Vendors",
        "active_tab": "vendors",
        "vendors": list(repository.list_vendors(connection)),
        "vendor_ip_counts": repository.list_vendor_ip_counts(connection),
        "errors": errors or [],
        "form_state": form_state or {"name": ""},
        "edit_errors": edit_errors or [],
        "edit_vendor": edit_vendor,
        "edit_form_state": edit_form_state
        or {"name": edit_vendor.name if edit_vendor else ""},
        "delete_errors": delete_errors or [],
        "delete_vendor": delete_vendor,
        "delete_confirm_value": delete_confirm_value,
    }
