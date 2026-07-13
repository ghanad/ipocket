from __future__ import annotations

from typing import Optional

from app.models import IPAssetType


def _default_vcenter_form_state() -> dict[str, object]:
    return {
        "server": "",
        "username": "",
        "password": "",
        "port": "443",
        "insecure": False,
        "mode": "dry-run",
    }


def _default_prometheus_form_state() -> dict[str, object]:
    return {
        "prometheus_url": "",
        "query": "",
        "ip_label": "instance",
        "asset_type": IPAssetType.OTHER.value,
        "project_name": "",
        "tags": "",
        "token": "",
        "insecure": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _default_elasticsearch_form_state() -> dict[str, object]:
    return {
        "elasticsearch_url": "",
        "username": "",
        "password": "",
        "api_key": "",
        "asset_type": IPAssetType.OTHER.value,
        "project_name": "",
        "tags": "",
        "note": "",
        "include_cluster_name_tag": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _default_cassandra_form_state() -> dict[str, object]:
    return {
        "contact_points": "",
        "port": "9042",
        "username": "",
        "password": "",
        "use_tls": False,
        "insecure": False,
        "asset_type": IPAssetType.OTHER.value,
        "project_name": "",
        "tags": "",
        "note": "",
        "include_cluster_name_tag": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _default_ceph_form_state() -> dict[str, object]:
    return {
        "ceph_url": "",
        "username": "",
        "password": "",
        "insecure": False,
        "asset_type": IPAssetType.OTHER.value,
        "project_name": "",
        "tags": "",
        "note": "",
        "include_cluster_name_tag": False,
        "include_label_tags": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _default_kubernetes_form_state() -> dict[str, object]:
    return {
        "api_url": "",
        "token": "",
        "insecure": False,
        "asset_type": IPAssetType.OS.value,
        "project_name": "",
        "tags": "",
        "note": "",
        "cluster_name": "",
        "include_cluster_name_tag": False,
        "include_label_tags": False,
        "mode": "dry-run",
        "timeout": "30",
    }


def _connectors_context(
    *,
    active_tab: str = "overview",
    vcenter_form_state: Optional[dict[str, object]] = None,
    vcenter_errors: Optional[list[str]] = None,
    vcenter_logs: Optional[list[str]] = None,
    prometheus_form_state: Optional[dict[str, object]] = None,
    prometheus_errors: Optional[list[str]] = None,
    prometheus_logs: Optional[list[str]] = None,
    elasticsearch_form_state: Optional[dict[str, object]] = None,
    elasticsearch_errors: Optional[list[str]] = None,
    elasticsearch_logs: Optional[list[str]] = None,
    cassandra_form_state: Optional[dict[str, object]] = None,
    cassandra_errors: Optional[list[str]] = None,
    cassandra_logs: Optional[list[str]] = None,
    ceph_form_state: Optional[dict[str, object]] = None,
    ceph_errors: Optional[list[str]] = None,
    ceph_logs: Optional[list[str]] = None,
    kubernetes_form_state: Optional[dict[str, object]] = None,
    kubernetes_errors: Optional[list[str]] = None,
    kubernetes_logs: Optional[list[str]] = None,
    toast_messages: Optional[list[dict[str, str]]] = None,
    connector_job_poll_url: Optional[str] = None,
) -> dict[str, object]:
    return {
        "title": "ipocket - Connectors",
        "active_tab": active_tab,
        "vcenter_form_state": vcenter_form_state or _default_vcenter_form_state(),
        "vcenter_errors": vcenter_errors or [],
        "vcenter_logs": vcenter_logs or [],
        "prometheus_form_state": prometheus_form_state
        or _default_prometheus_form_state(),
        "prometheus_errors": prometheus_errors or [],
        "prometheus_logs": prometheus_logs or [],
        "elasticsearch_form_state": elasticsearch_form_state
        or _default_elasticsearch_form_state(),
        "elasticsearch_errors": elasticsearch_errors or [],
        "elasticsearch_logs": elasticsearch_logs or [],
        "cassandra_form_state": cassandra_form_state or _default_cassandra_form_state(),
        "cassandra_errors": cassandra_errors or [],
        "cassandra_logs": cassandra_logs or [],
        "ceph_form_state": ceph_form_state or _default_ceph_form_state(),
        "ceph_errors": ceph_errors or [],
        "ceph_logs": ceph_logs or [],
        "kubernetes_form_state": kubernetes_form_state
        or _default_kubernetes_form_state(),
        "kubernetes_errors": kubernetes_errors or [],
        "kubernetes_logs": kubernetes_logs or [],
        "toast_messages": toast_messages or [],
        "connector_job_poll_url": connector_job_poll_url,
    }
