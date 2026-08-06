from __future__ import annotations

from app import repository
from app.models import IPAssetType


def test_host_completion_cases_are_public_filtered_and_cursor_paginated(
    client, _setup_connection
):
    connection = _setup_connection()
    try:
        os_only = repository.create_host(connection, "os-only")
        bmc_only = repository.create_host(connection, "bmc-only")
        complete = repository.create_host(connection, "complete")
        empty = repository.create_host(connection, "empty")
        repository.create_ip_asset(
            connection, "10.12.0.1", IPAssetType.OS, host_id=os_only.id
        )
        repository.create_ip_asset(
            connection, "10.22.0.2", IPAssetType.BMC, host_id=bmc_only.id
        )
        repository.create_ip_asset(
            connection, "10.12.0.3", IPAssetType.OS, host_id=complete.id
        )
        repository.create_ip_asset(
            connection, "10.22.0.3", IPAssetType.BMC, host_id=complete.id
        )
    finally:
        connection.close()

    first_page = client.get("/api/host-completion/cases", params={"limit": 1})
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert [item["host_id"] for item in first_payload["items"]] == [os_only.id]
    assert first_payload["items"][0]["missing"] == "BMC"
    assert first_payload["next_cursor"] == os_only.id

    second_page = client.get(
        "/api/host-completion/cases",
        params={"limit": 1, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200
    assert [item["host_id"] for item in second_page.json()["items"]] == [bmc_only.id]
    assert second_page.json()["items"][0]["missing"] == "OS"
    assert second_page.json()["next_cursor"] is None

    missing_bmc = client.get("/api/host-completion/cases", params={"missing": "BMC"})
    assert [item["host_id"] for item in missing_bmc.json()["items"]] == [os_only.id]
    assert complete.id not in {item["host_id"] for item in missing_bmc.json()["items"]}
    assert empty.id not in {item["host_id"] for item in missing_bmc.json()["items"]}


def test_host_completion_examples_return_only_complete_hosts(client, _setup_connection):
    connection = _setup_connection()
    try:
        project = repository.create_project(connection, "core")
        complete = repository.create_host(connection, "complete")
        incomplete = repository.create_host(connection, "incomplete")
        repository.create_ip_asset(
            connection,
            "10.13.0.1",
            IPAssetType.OS,
            project_id=project.id,
            host_id=complete.id,
        )
        repository.create_ip_asset(
            connection, "10.23.0.1", IPAssetType.BMC, host_id=complete.id
        )
        repository.create_ip_asset(
            connection, "10.13.0.2", IPAssetType.OS, host_id=incomplete.id
        )
    finally:
        connection.close()

    response = client.get("/api/host-completion/examples")

    assert response.status_code == 200
    assert response.json()["next_cursor"] is None
    assert response.json()["items"] == [
        {
            "host_id": complete.id,
            "host_name": "complete",
            "vendor": None,
            "os_assets": [
                {
                    "id": response.json()["items"][0]["os_assets"][0]["id"],
                    "ip_address": "10.13.0.1",
                    "project_id": project.id,
                    "project_name": "core",
                }
            ],
            "bmc_assets": [
                {
                    "id": response.json()["items"][0]["bmc_assets"][0]["id"],
                    "ip_address": "10.23.0.1",
                    "project_id": None,
                    "project_name": None,
                }
            ],
        }
    ]


def test_host_completion_query_validation(client):
    assert (
        client.get("/api/host-completion/cases", params={"missing": "VM"}).status_code
        == 422
    )
    assert (
        client.get("/api/host-completion/cases", params={"limit": 0}).status_code == 422
    )
    assert (
        client.get("/api/host-completion/examples", params={"limit": 501}).status_code
        == 422
    )
