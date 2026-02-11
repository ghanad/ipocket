from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.imports.models import (
    ImportApplyResult,
    ImportEntitySummary,
    ImportIssue,
    ImportSummary,
)
from app.models import Host, IPAsset, IPAssetType
from app.routes.api import utils as api_utils


def _summary() -> ImportSummary:
    return ImportSummary(
        vendors=ImportEntitySummary(would_create=1, would_update=2, would_skip=3),
        projects=ImportEntitySummary(would_create=4, would_update=5, would_skip=6),
        hosts=ImportEntitySummary(would_create=7, would_update=8, would_skip=9),
        ip_assets=ImportEntitySummary(would_create=10, would_update=11, would_skip=12),
    )


def test_is_auto_host_for_bmc_enabled_respects_env(monkeypatch) -> None:
    monkeypatch.delenv("IPOCKET_AUTO_HOST_FOR_BMC", raising=False)
    assert api_utils.is_auto_host_for_bmc_enabled() is True

    for value in ("0", "false", "no", "off"):
        monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", value)
        assert api_utils.is_auto_host_for_bmc_enabled() is False

    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "1")
    assert api_utils.is_auto_host_for_bmc_enabled() is True


def test_host_asset_and_metrics_payloads() -> None:
    host = Host(id=1, name="edge-01", notes="primary", vendor="Dell")
    host_data = api_utils.host_payload(host)
    assert host_data == {
        "id": 1,
        "name": "edge-01",
        "notes": "primary",
        "vendor": "Dell",
    }

    asset = IPAsset(
        id=2,
        ip_address="10.0.0.10",
        asset_type=IPAssetType.VM,
        project_id=10,
        host_id=1,
        notes="n",
        archived=False,
        created_at="c",
        updated_at="u",
    )
    asset_data = api_utils.asset_payload(asset, tags=["prod", "edge"])
    assert asset_data["type"] == "VM"
    assert asset_data["tags"] == ["prod", "edge"]

    assert api_utils.asset_payload(asset)["tags"] == []

    metrics_text = api_utils.metrics_payload(
        {
            "total": 5,
            "archived_total": 1,
            "unassigned_project_total": 2,
            "unassigned_owner_total": 3,
            "unassigned_both_total": 4,
        }
    )
    assert "ipam_ip_total 5" in metrics_text
    assert "ipam_ip_unassigned_both_total 4" in metrics_text


def test_summary_and_import_result_payload() -> None:
    summary = _summary()
    summary_data = api_utils.summary_payload(summary)
    assert summary_data["vendors"]["would_create"] == 1
    assert summary_data["total"]["would_update"] == 26

    result = ImportApplyResult(
        summary=summary,
        errors=[ImportIssue(location="bundle", message="bad")],
        warnings=[ImportIssue(location="bundle", message="warn")],
    )
    payload = api_utils.import_result_payload(result)
    assert payload["errors"][0]["message"] == "bad"
    assert payload["warnings"][0]["message"] == "warn"


def test_normalize_asset_type_value_valid_and_invalid() -> None:
    assert api_utils.normalize_asset_type_value("VM") == IPAssetType.VM
    assert api_utils.normalize_asset_type_value("IPMI_ILO") == IPAssetType.BMC

    with pytest.raises(HTTPException) as exc:
        api_utils.normalize_asset_type_value("BAD")
    assert exc.value.status_code == 422
    assert "Invalid asset type" in str(exc.value.detail)


def test_expand_csv_query_values_and_sd_token_guard() -> None:
    assert api_utils.expand_csv_query_values(None) == []
    assert api_utils.expand_csv_query_values([]) == []
    assert api_utils.expand_csv_query_values(["a,b", " c ", "", "d, e"]) == [
        "a",
        "b",
        "c",
        "d",
        "e",
    ]

    api_utils.require_sd_token_if_configured(None, None)
    api_utils.require_sd_token_if_configured("token", "token")

    with pytest.raises(HTTPException) as exc:
        api_utils.require_sd_token_if_configured("wrong", "expected")
    assert exc.value.status_code == 401
