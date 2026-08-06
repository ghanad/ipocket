from __future__ import annotations

from app.services import host_completion


def test_analytics_handles_null_types_missing_hosts_and_invalid_addresses(
    monkeypatch,
):
    monkeypatch.setattr(
        host_completion.repository,
        "get_host_completion_analytics_source",
        lambda _connection: {
            "host_ids": [1, 2],
            "assets": [
                {"host_id": 1, "ip_address": "not-an-ip", "type": "OS"},
                {"host_id": 1, "ip_address": "10.30.0.1", "type": "BMC"},
                {"host_id": None, "ip_address": "10.40.0.1", "type": None},
                {"host_id": 999, "ip_address": "10.40.0.2", "type": "VM"},
            ],
        },
    )

    analytics = host_completion.get_analytics(object())

    assert analytics == {
        "total_hosts": 2,
        "complete_hosts": 1,
        "incomplete_hosts": 1,
        "breakdown": {"os_only": 0, "bmc_only": 0, "unlinked": 1},
        "confirmed_pairs": 1,
        "patterns": [],
        "ip_type_counts": {"BMC": 1, "OS": 1, "VM": 1, "unknown": 1},
    }


def test_analytics_counts_every_os_bmc_combination_as_a_confirmed_pair(monkeypatch):
    monkeypatch.setattr(
        host_completion.repository,
        "get_host_completion_analytics_source",
        lambda _connection: {
            "host_ids": [1],
            "assets": [
                {"host_id": 1, "ip_address": "10.10.1.1", "type": "OS"},
                {"host_id": 1, "ip_address": "10.10.1.2", "type": "OS"},
                {"host_id": 1, "ip_address": "10.30.1.1", "type": "BMC"},
                {"host_id": 1, "ip_address": "10.30.1.2", "type": "BMC"},
            ],
        },
    )

    analytics = host_completion.get_analytics(object())

    assert analytics["complete_hosts"] == 1
    assert analytics["confirmed_pairs"] == 4
    assert analytics["patterns"] == [
        {
            "source_prefix": "10.10.0.0/16",
            "target_prefix": "10.30.0.0/16",
            "support": 2,
            "contradictions": 2,
            "coverage_percent": 50.0,
        }
    ]
