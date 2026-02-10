from __future__ import annotations

import sqlite3

import pytest

from app.models import IPAssetType, UserRole
from app.repository import (
    archive_ip_asset,
    bulk_update_ip_assets,
    count_active_ip_assets,
    count_audit_logs,
    count_hosts,
    create_host,
    create_ip_asset,
    create_ip_range,
    create_project,
    create_tag,
    create_user,
    create_vendor,
    delete_host,
    delete_ip_asset,
    delete_ip_range,
    delete_tag,
    get_audit_logs_for_ip,
    get_host_by_name,
    get_ip_asset_by_ip,
    get_ip_asset_metrics,
    get_ip_range_address_breakdown,
    get_ip_range_by_id,
    get_ip_range_utilization,
    get_management_summary,
    list_active_ip_assets_paginated,
    list_audit_logs,
    list_audit_logs_paginated,
    list_host_pair_ips_for_hosts,
    list_hosts,
    list_hosts_with_ip_counts,
    list_hosts_with_ip_counts_paginated,
    list_tags,
    list_tags_for_ip_assets,
    update_ip_asset,
    update_ip_range,
    update_project,
    update_tag,
)
from app.utils import normalize_tag_name


def test_tag_normalization_rules() -> None:
    assert normalize_tag_name(" Prod ") == "prod"
    with pytest.raises(ValueError):
        normalize_tag_name("bad tag")

def test_create_update_delete_tag(_setup_connection) -> None:
    connection = _setup_connection()
    tag = create_tag(connection, name="prod", color="#22c55e")
    assert tag.color == "#22c55e"

    updated = update_tag(connection, tag.id, name="prod", color="#0ea5e9")
    assert updated is not None
    assert updated.color == "#0ea5e9"

    tags = list(list_tags(connection))
    assert tags[0].name == "prod"

    deleted = delete_tag(connection, tag.id)
    assert deleted is True

