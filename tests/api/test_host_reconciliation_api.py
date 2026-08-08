from __future__ import annotations

import pytest

from app import repository
from app.models import IPAssetType, UserRole
from app.services import host_reconciliation


FINDINGS_URL = "/api/host-completion/findings"
DECISIONS_URL = "/api/host-completion/findings/decisions"
RULES_URL = "/api/host-completion/rules"


def _seed_create_host_finding(connection, *, archived_candidate: bool = False):
    """Seed three confirmed pairs plus an active, unlinked candidate pair."""

    for index in range(1, 4):
        host = repository.create_host(connection, f"confirmed-{index}")
        repository.create_ip_asset(
            connection, f"10.10.{index}.{index}", IPAssetType.OS, host_id=host.id
        )
        repository.create_ip_asset(
            connection, f"10.30.{index}.{index}", IPAssetType.BMC, host_id=host.id
        )
    os_asset = repository.create_ip_asset(connection, "10.10.4.42", IPAssetType.OS)
    bmc_asset = repository.create_ip_asset(connection, "10.30.4.42", IPAssetType.BMC)
    if archived_candidate:
        repository.set_ip_asset_archived(connection, bmc_asset.ip_address, True)
    return os_asset, bmc_asset


def _headers_for(_create_user, _login, _auth_headers, *, username: str, role: UserRole):
    _create_user(username, "secret", role)
    return _auth_headers(_login(username, "secret"))


def _create_host_finding(client, headers):
    response = client.get(FINDINGS_URL, headers=headers)
    assert response.status_code == 200
    proposals = [
        item
        for item in response.json()["items"]
        if item["finding_type"] == "CREATE_HOST"
    ]
    assert len(proposals) == 1
    return proposals[0]


def _accept_payload(finding):
    return {
        "proposal_id": finding["proposal_id"],
        "inventory_fingerprint": finding["inventory_fingerprint"],
        "decision": "ACCEPT",
    }


def test_reconciliation_reads_require_auth_and_allow_viewers(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        _seed_create_host_finding(connection)
    finally:
        connection.close()
    viewer_headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="reconciliation-viewer",
        role=UserRole.VIEWER,
    )

    assert client.get(FINDINGS_URL).status_code == 401
    assert client.get("/api/host-completion/findings/next").status_code == 401
    assert client.get("/api/host-completion/summary").status_code == 401
    assert client.get(FINDINGS_URL, headers=viewer_headers).status_code == 200
    assert (
        client.get(
            "/api/host-completion/findings/next", headers=viewer_headers
        ).status_code
        == 200
    )
    assert (
        client.get("/api/host-completion/summary", headers=viewer_headers).status_code
        == 200
    )


def test_reconciliation_mutation_requires_editor(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        _seed_create_host_finding(connection)
    finally:
        connection.close()
    viewer_headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="decision-viewer",
        role=UserRole.VIEWER,
    )
    finding = _create_host_finding(client, viewer_headers)

    response = client.post(
        DECISIONS_URL, headers=viewer_headers, json=_accept_payload(finding)
    )

    assert response.status_code == 403


def test_superuser_can_manage_manual_rules_and_their_audit_history(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        os_asset = repository.create_ip_asset(connection, "10.10.4.42", IPAssetType.OS)
        bmc_asset = repository.create_ip_asset(
            connection, "10.30.4.42", IPAssetType.BMC
        )
    finally:
        connection.close()
    superuser_headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="rule-superuser",
        role=UserRole.SUPERUSER,
    )
    editor_headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="rule-editor",
        role=UserRole.EDITOR,
    )
    body = {
        "source_prefix": "10.10.0.0/16",
        "target_prefix": "10.30.0.0/16",
        "active": True,
        "notes": "Rack B management network",
    }

    assert client.post(RULES_URL, headers=editor_headers, json=body).status_code == 403
    created = client.post(RULES_URL, headers=superuser_headers, json=body)
    assert created.status_code == 201
    assert created.json() == {
        "id": 1,
        "source_prefix": "10.10.0.0/16",
        "target_prefix": "10.30.0.0/16",
        "prefix_length": 16,
        "active": True,
        "notes": "Rack B management network",
    }

    summary = client.get("/api/host-completion/summary", headers=editor_headers)
    assert summary.status_code == 200
    managed = next(rule for rule in summary.json()["rules"] if rule["id"] == "manual-1")
    assert managed["managed"] is True
    assert managed["notes"] == "Rack B management network"
    finding = next(
        item
        for item in summary.json()["findings"]
        if item["finding_type"] == "CREATE_HOST"
    )
    assert finding["assets"][0]["id"] == os_asset.id
    assert finding["assets"][1]["id"] == bmc_asset.id

    disabled = client.put(
        f"{RULES_URL}/1",
        headers=superuser_headers,
        json={**body, "active": False, "notes": "Retired rack"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False
    summary = client.get("/api/host-completion/summary", headers=editor_headers).json()
    assert not any(
        item["finding_type"] == "CREATE_HOST" for item in summary["findings"]
    )
    connection = _setup_connection()
    try:
        audits = connection.execute(
            "SELECT action, target_type FROM audit_logs WHERE target_type = 'HOST_COMPLETION_RULE'"
        ).fetchall()
    finally:
        connection.close()
    assert [(row["action"], row["target_type"]) for row in audits] == [
        ("CREATE", "HOST_COMPLETION_RULE"),
        ("UPDATE", "HOST_COMPLETION_RULE"),
    ]


def test_editor_accepts_one_create_host_finding_and_links_both_assets_atomically(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        os_asset, bmc_asset = _seed_create_host_finding(connection)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="reconciliation-editor",
        role=UserRole.EDITOR,
    )
    finding = _create_host_finding(client, headers)
    connection = _setup_connection()
    try:
        audit_count_before = connection.execute(
            "SELECT COUNT(*) FROM audit_logs"
        ).fetchone()[0]
    finally:
        connection.close()

    response = client.post(
        DECISIONS_URL, headers=headers, json=_accept_payload(finding)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "ACCEPT"
    assert payload["idempotent_replay"] is False
    connection = _setup_connection()
    try:
        host = repository.get_host_by_name(connection, "server_10.30.4.42")
        refreshed_os = repository.get_ip_asset_by_ip(connection, os_asset.ip_address)
        refreshed_bmc = repository.get_ip_asset_by_ip(connection, bmc_asset.ip_address)
        decisions = connection.execute(
            "SELECT COUNT(*) FROM host_completion_decisions"
        ).fetchone()[0]
        audits = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    finally:
        connection.close()
    assert host is not None
    assert refreshed_os is not None and refreshed_os.host_id == host.id
    assert refreshed_bmc is not None and refreshed_bmc.host_id == host.id
    assert decisions == 1
    assert audits == audit_count_before + 4  # two links, the decision, and the new Host


def test_accept_reuses_the_template_named_host_without_creating_a_duplicate(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        os_asset, bmc_asset = _seed_create_host_finding(connection)
        existing = repository.create_host(connection, "server_10.30.4.42")
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="reuse-editor",
        role=UserRole.EDITOR,
    )
    finding = _create_host_finding(client, headers)

    response = client.post(
        DECISIONS_URL, headers=headers, json=_accept_payload(finding)
    )

    assert response.status_code == 200
    assert response.json()["host_id"] == existing.id
    connection = _setup_connection()
    try:
        host_count = connection.execute(
            "SELECT COUNT(*) FROM hosts WHERE lower(name) = lower(?)",
            ("server_10.30.4.42",),
        ).fetchone()[0]
        refreshed_os = repository.get_ip_asset_by_ip(connection, os_asset.ip_address)
        refreshed_bmc = repository.get_ip_asset_by_ip(connection, bmc_asset.ip_address)
    finally:
        connection.close()
    assert host_count == 1
    assert refreshed_os is not None and refreshed_os.host_id == existing.id
    assert refreshed_bmc is not None and refreshed_bmc.host_id == existing.id


def test_failure_after_first_link_rolls_back_host_links_decision_and_audits(
    client, _setup_connection, _create_user, _login, _auth_headers, monkeypatch
):
    connection = _setup_connection()
    try:
        os_asset, bmc_asset = _seed_create_host_finding(connection)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="rollback-editor",
        role=UserRole.EDITOR,
    )
    finding = _create_host_finding(client, headers)
    connection = _setup_connection()
    try:
        audit_count_before = connection.execute(
            "SELECT COUNT(*) FROM audit_logs"
        ).fetchone()[0]
    finally:
        connection.close()

    def fail_after_first_link(_asset):
        raise RuntimeError("injected post-link failure")

    monkeypatch.setattr(host_reconciliation, "_after_asset_link", fail_after_first_link)
    with pytest.raises(RuntimeError, match="injected post-link failure"):
        client.post(DECISIONS_URL, headers=headers, json=_accept_payload(finding))

    connection = _setup_connection()
    try:
        created_host = repository.get_host_by_name(connection, "server_10.30.4.42")
        refreshed_os = repository.get_ip_asset_by_ip(connection, os_asset.ip_address)
        refreshed_bmc = repository.get_ip_asset_by_ip(connection, bmc_asset.ip_address)
        decisions = connection.execute(
            "SELECT COUNT(*) FROM host_completion_decisions"
        ).fetchone()[0]
        audits = connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    finally:
        connection.close()
    assert created_host is None
    assert refreshed_os is not None and refreshed_os.host_id is None
    assert refreshed_bmc is not None and refreshed_bmc.host_id is None
    assert decisions == 0
    assert audits == audit_count_before


def test_repeat_decision_is_idempotent_and_does_not_duplicate_host_or_links(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        _seed_create_host_finding(connection)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="idempotency-editor",
        role=UserRole.EDITOR,
    )
    finding = _create_host_finding(client, headers)
    request_headers = {**headers, "Idempotency-Key": "same-reconciliation-decision"}

    first = client.post(
        DECISIONS_URL, headers=request_headers, json=_accept_payload(finding)
    )
    second = client.post(
        DECISIONS_URL, headers=request_headers, json=_accept_payload(finding)
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["idempotent_replay"] is True
    connection = _setup_connection()
    try:
        hosts = connection.execute(
            "SELECT COUNT(*) FROM hosts WHERE name = 'server_10.30.4.42'"
        ).fetchone()[0]
        decisions = connection.execute(
            "SELECT COUNT(*) FROM host_completion_decisions"
        ).fetchone()[0]
    finally:
        connection.close()
    assert hosts == decisions == 1


def test_stale_proposal_is_rejected_after_inventory_changes(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        _, bmc_asset = _seed_create_host_finding(connection)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="stale-editor",
        role=UserRole.EDITOR,
    )
    finding = _create_host_finding(client, headers)
    connection = _setup_connection()
    try:
        repository.set_ip_asset_archived(connection, bmc_asset.ip_address, True)
    finally:
        connection.close()

    response = client.post(
        DECISIONS_URL, headers=headers, json=_accept_payload(finding)
    )

    assert response.status_code == 409
    assert "stale" in response.json()["detail"].lower()


def test_archived_candidate_is_excluded_from_reconciliation_findings(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        os_asset, _ = _seed_create_host_finding(connection, archived_candidate=True)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="archived-viewer",
        role=UserRole.VIEWER,
    )

    findings = client.get(FINDINGS_URL, headers=headers).json()["items"]

    assert not any(item["finding_type"] == "CREATE_HOST" for item in findings)
    unmatched = next(
        item
        for item in findings
        if item["finding_type"] == "UNMATCHED_ASSET"
        and item["assets"][0]["id"] == os_asset.id
    )
    assert unmatched["state"] == "UNMATCHED"


@pytest.mark.parametrize(
    ("known_ip", "known_type", "counterpart_ip", "counterpart_type"),
    [
        ("10.10.9.90", IPAssetType.OS, "10.30.9.90", "BMC"),
        ("10.30.8.80", IPAssetType.BMC, "10.10.8.80", "OS"),
    ],
)
def test_manual_counterpart_ip_creates_missing_asset_and_convention_named_host(
    client,
    _setup_connection,
    _create_user,
    _login,
    _auth_headers,
    known_ip,
    known_type,
    counterpart_ip,
    counterpart_type,
):
    connection = _setup_connection()
    try:
        known = repository.create_ip_asset(connection, known_ip, known_type)
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username=f"manual-{counterpart_type.lower()}-editor",
        role=UserRole.EDITOR,
    )
    findings = client.get(FINDINGS_URL, headers=headers).json()["items"]
    finding = next(
        item
        for item in findings
        if item["finding_type"] == "UNMATCHED_ASSET"
        and item["assets"][0]["id"] == known.id
    )

    response = client.post(
        DECISIONS_URL,
        headers=headers,
        json={
            "proposal_id": finding["proposal_id"],
            "inventory_fingerprint": finding["inventory_fingerprint"],
            "decision": "CORRECT",
            "counterpart_ip": counterpart_ip,
            "counterpart_type": counterpart_type,
        },
    )

    assert response.status_code == 200
    bmc_ip = counterpart_ip if counterpart_type == "BMC" else known_ip
    connection = _setup_connection()
    try:
        host = repository.get_host_by_name(connection, f"server_{bmc_ip}")
        known_after = repository.get_ip_asset_by_ip(connection, known_ip)
        counterpart = repository.get_ip_asset_by_ip(connection, counterpart_ip)
    finally:
        connection.close()
    assert host is not None
    assert known_after is not None and known_after.host_id == host.id
    assert counterpart is not None and counterpart.host_id == host.id
    assert counterpart.asset_type == IPAssetType(counterpart_type)


def test_manual_bmc_address_reuses_existing_convention_named_host(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        known = repository.create_ip_asset(connection, "10.10.7.70", IPAssetType.OS)
        existing = repository.create_host(connection, "server_10.30.7.70")
    finally:
        connection.close()
    headers = _headers_for(
        _create_user,
        _login,
        _auth_headers,
        username="manual-reuse-editor",
        role=UserRole.EDITOR,
    )
    finding = next(
        item
        for item in client.get(FINDINGS_URL, headers=headers).json()["items"]
        if item["assets"][0]["id"] == known.id
    )

    response = client.post(
        DECISIONS_URL,
        headers=headers,
        json={
            "proposal_id": finding["proposal_id"],
            "inventory_fingerprint": finding["inventory_fingerprint"],
            "decision": "CORRECT",
            "counterpart_ip": "10.30.7.70",
            "counterpart_type": "BMC",
        },
    )

    assert response.status_code == 200
    assert response.json()["host_id"] == existing.id
    connection = _setup_connection()
    try:
        host_count = connection.execute(
            "SELECT COUNT(*) FROM hosts WHERE name = ?", ("server_10.30.7.70",)
        ).fetchone()[0]
    finally:
        connection.close()
    assert host_count == 1
