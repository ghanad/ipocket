from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import IPAssetType
from app.routes.api.schemas import (
    IPAssetCreate,
    IPAssetUpdate,
    ProjectCreate,
    ProjectUpdate,
)


def test_ip_asset_create_tags_and_type_validation_paths() -> None:
    model = IPAssetCreate(ip_address="10.1.1.1", type="IPMI_ILO", tags="Prod, edge")
    assert model.type == IPAssetType.BMC
    assert model.tags == ["prod", "edge"]

    with_none_tags = IPAssetCreate(ip_address="10.1.1.2", type="VM", tags=None)
    assert with_none_tags.tags is None

    with pytest.raises(ValidationError) as invalid_tags:
        IPAssetCreate(ip_address="10.1.1.3", type="VM", tags=123)
    assert "Tags must be a list or comma-separated string." in str(invalid_tags.value)

    with pytest.raises(ValidationError) as invalid_tag_name:
        IPAssetCreate(ip_address="10.1.1.4", type="VM", tags=["bad tag"])
    assert "Tag name may include letters, digits, dash, and underscore only." in str(
        invalid_tag_name.value
    )


def test_ip_asset_update_optional_type_and_tags_validation_paths() -> None:
    with_none = IPAssetUpdate(type=None, tags=None)
    assert with_none.type is None
    assert with_none.tags is None

    with_tags = IPAssetUpdate(type="VM", tags="edge,core")
    assert with_tags.type == IPAssetType.VM
    assert with_tags.tags == ["edge", "core"]

    with pytest.raises(ValidationError) as invalid_tags:
        IPAssetUpdate(tags=123)
    assert "Tags must be a list or comma-separated string." in str(invalid_tags.value)

    with pytest.raises(ValidationError) as invalid_tag_name:
        IPAssetUpdate(tags=["bad tag"])
    assert "Tag name may include letters, digits, dash, and underscore only." in str(
        invalid_tag_name.value
    )


def test_project_color_validators_raise_clean_errors() -> None:
    valid_create = ProjectCreate(name="Core", color="#ABCDEF")
    assert valid_create.color == "#abcdef"

    valid_update = ProjectUpdate(color="#123456")
    assert valid_update.color == "#123456"

    with pytest.raises(ValidationError) as invalid_create:
        ProjectCreate(name="Core", color="not-a-color")
    assert "Color must be a hex value like #1a2b3c." in str(invalid_create.value)

    with pytest.raises(ValidationError) as invalid_update:
        ProjectUpdate(color="not-a-color")
    assert "Color must be a hex value like #1a2b3c." in str(invalid_update.value)
