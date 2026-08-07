from __future__ import annotations

import os

import pytest

from app import db, repository
from app.main import app
from app.models import IPAssetType, User, UserRole
from app.routes.api.dependencies import require_authenticated_api_or_ui_session


@pytest.fixture(autouse=True)
def _authenticated_legacy_reads():
    app.dependency_overrides[require_authenticated_api_or_ui_session] = lambda: User(
        1, "legacy-viewer", "x", UserRole.VIEWER, True
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_authenticated_api_or_ui_session, None)


def _seed_rule(connection):
    for index in range(1, 4):
        host = repository.create_host(connection, f"example-{index}")
        repository.create_ip_asset(
            connection, f"10.10.{index}.{index}", IPAssetType.OS, host_id=host.id
        )
        repository.create_ip_asset(
            connection, f"10.30.{index}.{index}", IPAssetType.BMC, host_id=host.id
        )


def _editor_headers(_create_user, _login, _auth_headers):
    _create_user("completion-editor", "secret", UserRole.EDITOR)
    return _auth_headers(_login("completion-editor", "secret"))


def _decision_rows():
    connection = db.connect(os.environ["IPAM_DB_PATH"])
    try:
        return connection.execute(
            "SELECT host_id, mode, candidate_ip, corrected_ip, decision, decided_by "
            "FROM host_completion_decisions ORDER BY id"
        ).fetchall()
    finally:
        connection.close()


def test_editor_ui_session_can_record_review_decision(
    client, _setup_connection, _create_user
):
    connection = _setup_connection()
    try:
        target = repository.create_host(connection, "browser-review-target")
        repository.create_ip_asset(
            connection, "10.10.9.90", IPAssetType.OS, host_id=target.id
        )
    finally:
        connection.close()
    _create_user("browser-editor", "secret", UserRole.EDITOR)
    login = client.post(
        "/api/ui/login",
        json={"username": "browser-editor", "password": "secret"},
    )

    response = client.post(
        "/api/host-completion/decisions",
        json={
            "host_id": target.id,
            "mode": "ASK",
            "decision": "UNSURE",
        },
    )

    assert login.status_code == 200
    assert response.status_code == 200
    assert response.json()["decision"] == "UNSURE"


def test_review_queue_suggests_best_active_rule(client, _setup_connection):
    connection = _setup_connection()
    try:
        _seed_rule(connection)
        target = repository.create_host(connection, "target")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
    finally:
        connection.close()

    response = client.get("/api/host-completion/review-queue")

    assert response.status_code == 200
    assert response.json()["item"] == {
        "case_type": "HOST_MISSING_BMC",
        "host_id": target.id,
        "os_asset": {"address": "10.10.9.9", "hostname": None},
        "bmc_asset": None,
        "would_create_host": False,
        "mode": "SUGGEST",
        "candidate_ip": "10.30.9.9",
        "confidence": pytest.approx(0.85),
        "evidence": [
            "10.10.1.1 -> 10.30.1.1",
            "10.10.2.2 -> 10.30.2.2",
            "10.10.3.3 -> 10.30.3.3",
        ],
        "reason_text": ("3 confirmed hosts use mapping 10.10.0.0/16 -> 10.30.0.0/16"),
        "host_name_template": "server_{bmc}",
        "host_options": response.json()["item"]["host_options"],
    }
    assert response.json()["remaining"] == 0
    assert response.json()["item"]["host_options"][0]["id"] == target.id


@pytest.mark.parametrize(
    ("asset_type", "linked_elsewhere", "reason"),
    [
        (IPAssetType.BMC, True, "already linked to another host"),
        (IPAssetType.VM, False, "exists as a VM asset"),
    ],
)
def test_review_queue_safety_checks_existing_candidate(
    client,
    _setup_connection,
    asset_type,
    linked_elsewhere,
    reason,
):
    connection = _setup_connection()
    try:
        _seed_rule(connection)
        target = repository.create_host(connection, f"target-{asset_type.value}")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
        other = (
            repository.create_host(connection, "other") if linked_elsewhere else None
        )
        repository.create_ip_asset(
            connection,
            "10.30.9.9",
            asset_type,
            host_id=other.id if other else None,
        )
    finally:
        connection.close()

    item = client.get("/api/host-completion/review-queue").json()["item"]

    assert item["mode"] == "ASK"
    assert reason in item["reason_text"]
    assert item["candidate_ip"] is None


def test_review_queue_skips_unsafe_rule_and_uses_next_active_rule(
    client, _setup_connection
):
    connection = _setup_connection()
    try:
        for target_prefix in (30, 40):
            for index in range(1, 4):
                host = repository.create_host(
                    connection, f"example-{target_prefix}-{index}"
                )
                repository.create_ip_asset(
                    connection,
                    f"10.10.{target_prefix}.{index}",
                    IPAssetType.OS,
                    host_id=host.id,
                )
                repository.create_ip_asset(
                    connection,
                    f"10.{target_prefix}.{target_prefix}.{index}",
                    IPAssetType.BMC,
                    host_id=host.id,
                )
        target = repository.create_host(connection, "fallback-target")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
        conflict_host = repository.create_host(connection, "fallback-conflict")
        repository.create_ip_asset(
            connection, "10.30.9.9", IPAssetType.BMC, host_id=conflict_host.id
        )
    finally:
        connection.close()

    item = client.get("/api/host-completion/review-queue").json()["item"]

    assert item["mode"] == "SUGGEST"
    assert item["candidate_ip"] == "10.40.9.9"


def test_reject_is_stored_and_candidate_never_returns(
    client,
    _setup_connection,
    _create_user,
    _login,
    _auth_headers,
):
    connection = _setup_connection()
    try:
        _seed_rule(connection)
        target = repository.create_host(connection, "reject-target")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    response = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "host_id": target.id,
            "mode": "SUGGEST",
            "decision": "REJECT",
            "candidate_ip": "10.30.9.9",
        },
    )

    assert response.status_code == 200
    assert response.json()["applied_ip"] is None
    item = client.get("/api/host-completion/review-queue").json()["item"]
    assert item["mode"] == "ASK"
    assert "previously rejected" in item["reason_text"]
    assert _decision_rows()[0][4] == "REJECT"


def test_accept_creates_audited_bmc_asset(
    client,
    _setup_connection,
    _create_user,
    _login,
    _auth_headers,
):
    connection = _setup_connection()
    try:
        target = repository.create_host(connection, "accept-target")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    response = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "host_id": target.id,
            "mode": "SUGGEST",
            "decision": "ACCEPT",
            "candidate_ip": "10.30.9.9",
        },
    )

    assert response.status_code == 200
    connection = _setup_connection()
    try:
        asset = repository.get_ip_asset_by_ip(connection, "10.30.9.9")
        audits = repository.get_audit_logs_for_ip(connection, asset.id if asset else -1)
    finally:
        connection.close()
    assert asset is not None
    assert (asset.asset_type, asset.host_id) == (IPAssetType.BMC, target.id)
    assert any(audit.action == "CREATE" for audit in audits)
    assert _decision_rows()[0][4] == "ACCEPT"


def test_corrected_links_existing_asset_and_validates_conflicts(
    client,
    _setup_connection,
    _create_user,
    _login,
    _auth_headers,
):
    connection = _setup_connection()
    try:
        target = repository.create_host(connection, "corrected-target")
        repository.create_ip_asset(connection, "10.40.9.9", IPAssetType.OTHER)
        other = repository.create_host(connection, "corrected-other")
        repository.create_ip_asset(
            connection, "10.40.9.10", IPAssetType.BMC, host_id=other.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    invalid = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "host_id": target.id,
            "mode": "ASK",
            "decision": "CORRECTED",
            "corrected_ip": "not-an-ip",
        },
    )
    conflict = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "host_id": target.id,
            "mode": "ASK",
            "decision": "CORRECTED",
            "corrected_ip": "10.40.9.10",
        },
    )
    applied = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "host_id": target.id,
            "mode": "ASK",
            "decision": "CORRECTED",
            "candidate_ip": "10.30.9.9",
            "corrected_ip": "10.40.9.9",
        },
    )

    assert invalid.status_code == 422
    assert conflict.status_code == 409
    assert applied.status_code == 200
    connection = _setup_connection()
    try:
        asset = repository.get_ip_asset_by_ip(connection, "10.40.9.9")
        audits = repository.get_audit_logs_for_ip(connection, asset.id if asset else -1)
    finally:
        connection.close()
    assert asset is not None
    assert (asset.asset_type, asset.host_id) == (IPAssetType.BMC, target.id)
    assert any(audit.action == "UPDATE" for audit in audits)
    row = _decision_rows()[0]
    assert (row[2], row[3], row[4]) == ("10.30.9.9", "10.40.9.9", "CORRECTED")


@pytest.mark.parametrize("decision", ["UNSURE", "NO_BMC"])
def test_unsure_is_deferred_and_no_bmc_excludes_host_from_queue(
    client,
    _setup_connection,
    _create_user,
    _login,
    _auth_headers,
    decision,
):
    connection = _setup_connection()
    try:
        target = repository.create_host(connection, f"{decision.lower()}-target")
        repository.create_ip_asset(
            connection, "10.10.9.9", IPAssetType.OS, host_id=target.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    response = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={"host_id": target.id, "mode": "ASK", "decision": decision},
    )

    assert response.status_code == 200
    queue = client.get("/api/host-completion/review-queue").json()
    if decision == "NO_BMC":
        assert queue == {"item": None, "remaining": 0}
    else:
        assert queue["item"]["case_type"] == "HOST_MISSING_BMC"
    assert _decision_rows()[0][4] == decision


def test_queue_prioritizes_source_16_with_most_incomplete_hosts(
    client, _setup_connection
):
    connection = _setup_connection()
    try:
        first = repository.create_host(connection, "small-prefix")
        repository.create_ip_asset(
            connection, "10.11.1.1", IPAssetType.OS, host_id=first.id
        )
        for index in range(2):
            host = repository.create_host(connection, f"large-prefix-{index}")
            repository.create_ip_asset(
                connection, f"10.12.1.{index + 1}", IPAssetType.OS, host_id=host.id
            )
    finally:
        connection.close()

    payload = client.get("/api/host-completion/review-queue").json()

    assert payload["item"]["os_asset"]["address"] == "10.12.1.1"
    assert payload["remaining"] == 2


def test_queue_handles_mixed_ipv4_and_ipv6_os_assets(client, _setup_connection):
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, "mixed-address-family")
        repository.create_ip_asset(
            connection, "2001:db8::1", IPAssetType.OS, host_id=host.id
        )
        repository.create_ip_asset(
            connection, "10.10.1.1", IPAssetType.OS, host_id=host.id
        )
    finally:
        connection.close()

    response = client.get("/api/host-completion/review-queue")

    assert response.status_code == 200
    assert response.json()["item"]["os_asset"]["address"] == "10.10.1.1"


def test_unlinked_pair_is_consumed_once_and_accept_is_idempotent(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        for source_second in (10, 11):
            for index in range(1, 4):
                host_bits = index if source_second == 10 else index + 10
                host = repository.create_host(
                    connection, f"pair-{source_second}-{index}"
                )
                repository.create_ip_asset(
                    connection,
                    f"10.{source_second}.{host_bits}.{host_bits}",
                    IPAssetType.OS,
                    host_id=host.id,
                )
                repository.create_ip_asset(
                    connection,
                    f"10.30.{host_bits}.{host_bits}",
                    IPAssetType.BMC,
                    host_id=host.id,
                )
        repository.create_ip_asset(connection, "10.10.9.9", IPAssetType.OS)
        repository.create_ip_asset(connection, "10.11.9.9", IPAssetType.OS)
        repository.create_ip_asset(connection, "10.30.9.9", IPAssetType.BMC)
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    payload = client.get("/api/host-completion/review-queue").json()
    item = payload["item"]
    assert item["case_type"] == "UNLINKED_OS_PAIR"
    assert item["confidence"] == pytest.approx(0.9)
    assert payload["remaining"] == 1

    decision = {
        "case_type": item["case_type"],
        "mode": item["mode"],
        "os_address": item["os_asset"]["address"],
        "bmc_address": item["bmc_asset"]["address"],
        "decision": "ACCEPT",
        "host_name": "paired-unlinked",
    }
    first = client.post(
        "/api/host-completion/decisions", headers=headers, json=decision
    )
    second = client.post(
        "/api/host-completion/decisions", headers=headers, json=decision
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["host_id"] == second.json()["host_id"]
    connection = _setup_connection()
    try:
        assert [host.name for host in repository.list_hosts(connection)].count(
            "paired-unlinked"
        ) == 1
    finally:
        connection.close()


def test_extended_decisions_validate_host_name_attach_and_deactivate(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        repository.create_ip_asset(connection, "10.20.1.1", IPAssetType.OS)
        source = repository.create_host(connection, "attach-source")
        target = repository.create_host(connection, "attach-target")
        repository.create_ip_asset(
            connection, "10.20.1.2", IPAssetType.BMC, host_id=source.id
        )
        repository.create_ip_asset(connection, "10.20.1.3", IPAssetType.OS)
    finally:
        connection.close()

    headers = _editor_headers(_create_user, _login, _auth_headers)

    missing_name = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.20.1.1",
            "decision": "NO_BMC",
        },
    )
    no_bmc = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.20.1.1",
            "decision": "NO_BMC",
            "host_name": "no-bmc-host",
        },
    )
    conflict = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_BMC",
            "mode": "ASK",
            "bmc_address": "10.20.1.2",
            "target_host_id": target.id,
            "decision": "ATTACH_EXISTING",
        },
    )
    deactivated = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.20.1.3",
            "decision": "DEACTIVATE",
        },
    )

    assert missing_name.status_code == 422
    assert "host_name is required" in missing_name.json()["detail"]
    assert no_bmc.status_code == 200
    assert conflict.status_code == 409
    assert deactivated.status_code == 200


def test_existing_name_attaches_unlinked_assets_in_both_directions_and_is_idempotent(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        first = repository.create_host(connection, "server_10.30.1.1")
        repository.create_ip_asset(
            connection, "10.30.1.1", IPAssetType.BMC, host_id=first.id
        )
        repository.create_ip_asset(connection, "10.10.1.1", IPAssetType.OS)
        repository.create_ip_asset(connection, "10.30.2.2", IPAssetType.BMC)
        second = repository.create_host(connection, "server_10.30.2.2")
        repository.create_ip_asset(
            connection, "10.10.2.2", IPAssetType.OS, host_id=second.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    os_to_existing = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.10.1.1",
            "candidate_ip": "10.30.1.1",
            "decision": "ACCEPT",
            "host_name": " SERVER_10.30.1.1 ",
        },
    )
    bmc_to_existing = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_BMC",
            "mode": "ASK",
            "bmc_address": "10.30.2.2",
            "candidate_ip": "10.10.2.2",
            "decision": "ACCEPT",
            "host_name": "server_10.30.2.2",
        },
    )

    assert os_to_existing.status_code == bmc_to_existing.status_code == 200
    assert (
        "attached to existing host 'server_10.30.1.1'"
        in os_to_existing.json()["message"]
    )
    connection = _setup_connection()
    try:
        assert (
            repository.get_ip_asset_by_ip(connection, "10.10.1.1").host_id == first.id
        )
        assert (
            repository.get_ip_asset_by_ip(connection, "10.30.2.2").host_id == second.id
        )
    finally:
        connection.close()


def test_existing_name_rejects_a_different_bmc(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        host = repository.create_host(connection, "server_10.30.1.1")
        repository.create_ip_asset(
            connection, "10.30.1.1", IPAssetType.BMC, host_id=host.id
        )
        repository.create_ip_asset(connection, "10.10.1.2", IPAssetType.OS)
        repository.create_ip_asset(connection, "10.30.1.2", IPAssetType.BMC)
    finally:
        connection.close()
    response = client.post(
        "/api/host-completion/decisions",
        headers=_editor_headers(_create_user, _login, _auth_headers),
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.10.1.2",
            "candidate_ip": "10.30.1.2",
            "decision": "ACCEPT",
            "host_name": "server_10.30.1.1",
        },
    )
    assert response.status_code == 409
    assert "already has active BMC IP 10.30.1.1" in response.json()["detail"]


def test_name_derived_bmc_suggestion_and_ignored_nonmatches(
    client, _setup_connection, monkeypatch
):
    monkeypatch.setenv("HOST_NAME_TEMPLATE", "server_{bmc}")
    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "0")
    connection = _setup_connection()
    try:
        target = repository.create_host(connection, "server_10.30.9.9")
        repository.create_ip_asset(connection, "10.30.9.9", IPAssetType.BMC)
        linked_elsewhere = repository.create_host(connection, "server_10.30.8.8")
        repository.create_ip_asset(
            connection, "10.30.8.8", IPAssetType.BMC, host_id=linked_elsewhere.id
        )
        repository.create_host(connection, "not-a-template-name")
    finally:
        connection.close()

    queue = client.get("/api/host-completion/review-queue").json()
    item = queue["item"]
    assert item["host_id"] == target.id
    assert item["case_type"] == "HOST_MISSING_BMC"
    assert item["candidate_ip"] == "10.30.9.9"
    assert item["confidence"] == pytest.approx(0.95)
    assert item["evidence"] == ["host name encodes the BMC address"]


def test_host_autocomplete_orders_incomplete_then_recent_then_remaining(
    client, _setup_connection, _create_user, _login, _auth_headers
):
    connection = _setup_connection()
    try:
        complete = repository.create_host(connection, "complete")
        repository.create_ip_asset(
            connection, "10.10.3.1", IPAssetType.OS, host_id=complete.id
        )
        repository.create_ip_asset(
            connection, "10.30.3.1", IPAssetType.BMC, host_id=complete.id
        )
        incomplete = repository.create_host(connection, "incomplete")
        repository.create_ip_asset(
            connection, "10.10.2.1", IPAssetType.OS, host_id=incomplete.id
        )
        recent = repository.create_host(connection, "recent")
        repository.create_ip_asset(
            connection, "10.10.4.1", IPAssetType.OS, host_id=recent.id
        )
        repository.create_ip_asset(
            connection, "10.30.4.1", IPAssetType.BMC, host_id=recent.id
        )
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)
    client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "HOST_MISSING_BMC",
            "mode": "ASK",
            "host_id": recent.id,
            "decision": "UNSURE",
        },
    )

    options = client.get("/api/host-completion/review-queue").json()["item"][
        "host_options"
    ]
    names = [option["name"] for option in options]
    assert names.index("incomplete") < names.index("recent") < names.index("complete")


def test_cold_start_replay_creates_then_completes_template_named_host(
    client, _setup_connection, _create_user, _login, _auth_headers, monkeypatch
):
    monkeypatch.setenv("IPOCKET_AUTO_HOST_FOR_BMC", "0")
    connection = _setup_connection()
    try:
        repository.create_ip_asset(connection, "10.30.1.1", IPAssetType.BMC)
        repository.create_ip_asset(connection, "10.10.1.1", IPAssetType.OS)
    finally:
        connection.close()
    headers = _editor_headers(_create_user, _login, _auth_headers)

    created = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_BMC",
            "mode": "ASK",
            "bmc_address": "10.30.1.1",
            "decision": "CREATE_HOST_ONLY",
            "host_name": "server_10.30.1.1",
        },
    )
    attached = client.post(
        "/api/host-completion/decisions",
        headers=headers,
        json={
            "case_type": "UNLINKED_OS",
            "mode": "ASK",
            "os_address": "10.10.1.1",
            "candidate_ip": "10.30.1.1",
            "decision": "ACCEPT",
            "host_name": "server_10.30.1.1",
        },
    )

    assert created.status_code == attached.status_code == 200
    assert created.json()["host_id"] == attached.json()["host_id"]
    assert attached.json()["message"].endswith("Host is now complete.")
    assert client.get("/api/host-completion/analytics").json()["confirmed_pairs"] == 1
