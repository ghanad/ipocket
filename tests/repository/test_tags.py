from __future__ import annotations


import pytest

from app.models import IPAssetType
from app.repository import (
    archive_ip_asset,
    create_ip_asset,
    create_tag,
    delete_tag,
    list_tag_ip_counts,
    list_tags,
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


def test_list_tag_ip_counts_excludes_archived_assets(_setup_connection) -> None:
    connection = _setup_connection()
    create_tag(connection, name="prod")
    create_tag(connection, name="edge")

    active_asset = create_ip_asset(
        connection,
        ip_address="10.88.0.10",
        asset_type=IPAssetType.VM,
        tags=["prod", "edge"],
    )
    archived_asset = create_ip_asset(
        connection,
        ip_address="10.88.0.11",
        asset_type=IPAssetType.VM,
        tags=["prod"],
    )
    archive_ip_asset(connection, archived_asset.ip_address)

    counts = list_tag_ip_counts(connection)

    prod_tag = next(tag for tag in list_tags(connection) if tag.name == "prod")
    edge_tag = next(tag for tag in list_tags(connection) if tag.name == "edge")
    assert counts[prod_tag.id] == 1
    assert counts[edge_tag.id] == 1
    assert active_asset.id != archived_asset.id
