from __future__ import annotations

from ipocket_agent import (
    AgentDecision,
    Asset,
    Host,
    Inventory,
    discover_rules,
    reconcile,
)


def _asset(
    identifier: str,
    address: str,
    kind: str,
    host_id: str | None = None,
    *,
    archived: bool = False,
) -> Asset:
    return Asset(
        id=identifier,
        ip_address=address,
        asset_type=kind,
        host_id=host_id,
        archived=archived,
    )  # type: ignore[arg-type]


def _rule_inventory(
    *extra: Asset, decisions: tuple[AgentDecision, ...] = ()
) -> Inventory:
    hosts = tuple(
        Host(id=f"h{index}", name=f"confirmed-{index}") for index in range(1, 4)
    )
    assets = [
        item
        for index in range(1, 4)
        for item in (
            _asset(f"os{index}", f"10.10.{index}.{index}", "OS", f"h{index}"),
            _asset(f"bmc{index}", f"10.30.{index}.{index}", "BMC", f"h{index}"),
        )
    ]
    return Inventory(assets=tuple(assets) + extra, hosts=hosts, decisions=decisions)


def _find(result, kind: str):
    return [finding for finding in result.findings if finding.kind == kind]


def test_two_unlinked_matching_assets_create_one_host_proposal_without_opposite_duplicate():
    inventory = _rule_inventory(
        _asset("new-os", "10.10.4.42", "OS"),
        _asset("new-bmc", "10.30.4.42", "BMC"),
    )

    result = reconcile(inventory)

    proposals = _find(result, "CREATE_HOST")
    assert len(proposals) == 1
    assert proposals[0].asset_ids == ("new-bmc", "new-os")
    assert proposals[0].proposed_host_name == "server_10.30.4.42"
    assert proposals[0].strength == "STRONG"
    assert not _find(result, "UNMATCHED_ASSET")
    assert result.states["new-os"] == result.states["new-bmc"] == "PROPOSED"


def test_existing_host_with_only_bmc_gets_complete_host_proposal():
    inventory = _rule_inventory(
        _asset("candidate-os", "10.10.4.42", "OS"),
        _asset("known-bmc", "10.30.4.42", "BMC", "incomplete"),
    )
    inventory = Inventory(
        inventory.assets, inventory.hosts + (Host("incomplete", "server_10.30.4.42"),)
    )

    finding = _find(reconcile(inventory), "COMPLETE_HOST")[0]

    assert finding.host_id == "incomplete"
    assert set(finding.asset_ids) == {"candidate-os", "known-bmc"}


def test_existing_host_with_only_os_gets_complete_host_proposal():
    inventory = _rule_inventory(
        _asset("known-os", "10.10.4.42", "OS", "incomplete"),
        _asset("candidate-bmc", "10.30.4.42", "BMC"),
    )
    inventory = Inventory(
        inventory.assets, inventory.hosts + (Host("incomplete", "server_10.30.4.42"),)
    )

    finding = _find(reconcile(inventory), "COMPLETE_HOST")[0]

    assert finding.host_id == "incomplete"
    assert set(finding.asset_ids) == {"known-os", "candidate-bmc"}


def test_candidate_on_another_host_becomes_conflict_not_proposal():
    inventory = _rule_inventory(
        _asset("known-os", "10.10.4.42", "OS", "target"),
        _asset("claimed-bmc", "10.30.4.42", "BMC", "other"),
    )
    inventory = Inventory(
        inventory.assets,
        inventory.hosts + (Host("target", "target"), Host("other", "other")),
    )

    result = reconcile(inventory)

    assert not _find(result, "CREATE_HOST")
    assert any(
        "already attached" in finding.reasons[0]
        for finding in _find(result, "CONFLICT")
    )
    assert result.states["known-os"] == "CONFLICT"


def test_wrong_candidate_type_becomes_conflict_not_unsafe_suggestion():
    result = reconcile(
        _rule_inventory(
            _asset("new-os", "10.10.4.42", "OS"),
            _asset("wrong-type", "10.30.4.42", "OTHER"),
        )
    )

    assert not _find(result, "CREATE_HOST")
    assert any(
        "incompatible type OTHER" in finding.reasons[0]
        for finding in _find(result, "CONFLICT")
    )


def test_weak_evidence_is_unmatched_and_never_forces_a_match():
    inventory = Inventory(
        assets=(
            _asset("os1", "10.10.1.1", "OS", "h1"),
            _asset("bmc1", "10.30.1.1", "BMC", "h1"),
            _asset("os2", "10.10.2.2", "OS", "OS2"),
            _asset("bmc2", "10.30.2.2", "BMC", "OS2"),
            _asset("new-os", "10.10.4.42", "OS"),
            _asset("new-bmc", "10.30.4.42", "BMC"),
        ),
        hosts=(Host("h1", "one"), Host("OS2", "two")),
    )

    result = reconcile(inventory)

    assert not _find(result, "CREATE_HOST")
    assert {finding.asset_ids[0] for finding in _find(result, "UNMATCHED_ASSET")} >= {
        "new-os",
        "new-bmc",
    }


def test_wrong_pair_is_negative_evidence_and_suppresses_exact_match():
    inventory = _rule_inventory(
        _asset("new-os", "10.10.4.42", "OS"),
        _asset("new-bmc", "10.30.4.42", "BMC"),
        decisions=(
            AgentDecision("WRONG_PAIR", os_ip="10.10.4.42", bmc_ip="10.30.4.42"),
        ),
    )

    result = reconcile(inventory)

    assert not _find(result, "CREATE_HOST")
    assert any(rule.contradictions == 1 for rule in result.rules)
    assert result.states["new-os"] == "UNMATCHED"


def test_unsure_is_not_a_rule_contradiction():
    baseline = discover_rules(_rule_inventory())
    with_unsure = discover_rules(
        _rule_inventory(
            decisions=(
                AgentDecision("UNSURE", os_ip="10.10.4.42", bmc_ip="10.30.4.42"),
            )
        )
    )

    assert [(rule.id, rule.contradictions) for rule in with_unsure] == [
        (rule.id, rule.contradictions) for rule in baseline
    ]


def test_unsure_defers_the_same_finding_without_suppressing_it():
    inventory = _rule_inventory(
        _asset("first-os", "10.10.4.4", "OS"),
        _asset("first-bmc", "10.30.4.4", "BMC"),
        _asset("second-os", "10.10.5.5", "OS"),
        _asset("second-bmc", "10.30.5.5", "BMC"),
        decisions=(
            AgentDecision("UNSURE", asset_id="first-os"),
            AgentDecision("UNSURE", asset_id="first-bmc"),
        ),
    )

    findings = _find(reconcile(inventory), "CREATE_HOST")

    assert len(findings) == 2
    assert set(findings[0].asset_ids) == {"second-os", "second-bmc"}
    assert set(findings[1].asset_ids) == {"first-os", "first-bmc"}


def test_exception_is_not_a_rule_contradiction_and_is_a_distinct_state():
    inventory = _rule_inventory(
        _asset("exception-os", "10.10.4.42", "OS"),
        decisions=(AgentDecision("EXCEPTION", asset_id="exception-os"),),
    )

    result = reconcile(inventory)

    assert all(rule.contradictions == 0 for rule in result.rules if rule.support >= 3)
    assert result.states["exception-os"] == "EXCEPTION"
    assert result.kpis["explicit_exceptions"] == 1


def test_archived_assets_are_not_ordinary_candidates():
    result = reconcile(
        _rule_inventory(
            _asset("new-os", "10.10.4.42", "OS"),
            _asset("old-bmc", "10.30.4.42", "BMC", archived=True),
        )
    )

    assert not _find(result, "CREATE_HOST")
    assert result.states["new-os"] == "UNMATCHED"
    assert "old-bmc" not in result.states
