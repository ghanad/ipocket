from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.connectors.cassandra import CassandraConnectorError, parse_contact_points
from app.models import IPAssetType
from app.utils import split_tag_string

CONNECTOR_NAMES = (
    "vcenter",
    "prometheus",
    "elasticsearch",
    "cassandra",
    "ceph",
    "kubernetes",
)
SECRET_FIELDS = frozenset({"password", "token", "api_key", "authorization"})
ASSET_TYPES = tuple(item.value for item in IPAssetType)


@dataclass(frozen=True)
class ParsedConnectorRun:
    form_state: dict[str, object]
    task_kwargs: dict[str, object]
    mode: str


def _field(
    name: str,
    label: str,
    field_type: str = "text",
    *,
    required: bool = False,
    default: object = "",
    placeholder: str = "",
    span: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
    options: tuple[str, ...] = (),
    secret: bool = False,
) -> dict[str, object]:
    result: dict[str, object] = {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "default": "" if secret else default,
        "placeholder": placeholder,
        "span": span,
        "secret": secret,
    }
    if minimum is not None:
        result["min"] = minimum
    if maximum is not None:
        result["max"] = maximum
    if options:
        result["options"] = list(options)
    return result


MODE_FIELD = _field(
    "mode", "Mode", "select", default="dry-run", options=("dry-run", "apply")
)
ASSET_TYPE_FIELD = _field(
    "asset_type", "Asset type", "select", default="OTHER", options=ASSET_TYPES
)
TIMEOUT_FIELD = _field(
    "timeout", "Timeout (seconds)", "number", required=True, default="30", minimum=1
)


CONNECTOR_SCHEMAS: dict[str, dict[str, object]] = {
    "vcenter": {
        "display_name": "vCenter",
        "description": "Connect to vCenter and run import in dry-run or apply mode directly from UI.",
        "kind": "Manual CLI export",
        "help": "For full mapping/options, see /docs/vcenter-connector.md.",
        "command": "python -m app.connectors.vcenter --server <vcenter> --username <user> --password '<pass>' --output ./vcenter-bundle.json",
        "fields": [
            _field("server", "vCenter server", required=True, placeholder="vc.example.local", span=True),
            _field("port", "Port", "number", required=True, default="443", minimum=1, maximum=65535),
            MODE_FIELD,
            _field("username", "Username", required=True, placeholder="administrator@vsphere.local"),
            _field("password", "Password", "password", required=True, secret=True),
            _field("insecure", "Skip TLS verification", "checkbox", default=False, span=True),
        ],
    },
    "prometheus": {
        "display_name": "Prometheus",
        "description": "Query Prometheus, extract IPv4 addresses from a label, and import to ipocket.",
        "kind": "Query-based import",
        "help": "For full mapping/options, see /docs/prometheus-connector.md.",
        "command": "python -m app.connectors.prometheus --prometheus-url http://127.0.0.1:9090 --query 'up{job=\"node\"}' --ip-label instance --mode dry-run",
        "fields": [
            _field("prometheus_url", "Prometheus URL", "url", required=True, placeholder="http://127.0.0.1:9090", span=True),
            _field("query", "PromQL Query", required=True, placeholder='up{job="node"}', span=True),
            _field("ip_label", "IP label", required=True, default="instance", placeholder="instance"),
            ASSET_TYPE_FIELD,
            _field("project_name", "Project name (optional)", placeholder="Core"),
            _field("tags", "Tags (optional)", placeholder="monitoring,node-exporter"),
            _field("token", "Prometheus auth (optional)", "password", placeholder="token OR username:password", secret=True),
            TIMEOUT_FIELD,
            MODE_FIELD,
            _field("insecure", "Skip TLS verification", "checkbox", default=False, span=True),
        ],
    },
    "elasticsearch": {
        "display_name": "Elasticsearch",
        "description": "Read Elasticsearch node inventory and import node IP addresses to ipocket.",
        "kind": "Node inventory import",
        "help": "For full mapping/options, see /docs/elasticsearch-connector.md.",
        "command": "python -m app.connectors.elasticsearch --elasticsearch-url https://127.0.0.1:9200 --api-key '<base64-or-id:key>' --mode dry-run",
        "fields": [
            _field("elasticsearch_url", "Elasticsearch URL", "url", required=True, placeholder="https://127.0.0.1:9200", span=True),
            _field("username", "Username (optional)", placeholder="elastic"),
            _field("password", "Password (optional)", "password", placeholder="********", secret=True),
            _field("api_key", "API Key (optional)", "password", placeholder="base64 OR id:key", secret=True, span=True),
            ASSET_TYPE_FIELD,
            _field("project_name", "Project name (optional)", placeholder="Core"),
            _field("tags", "Tags (optional)", placeholder="elasticsearch,nodes"),
            _field("note", "Note (optional)", placeholder="Imported from Elasticsearch nodes"),
            _field("include_cluster_name_tag", "Add cluster name as tag", "checkbox", default=False, span=True),
            TIMEOUT_FIELD,
            MODE_FIELD,
        ],
    },
    "cassandra": {
        "display_name": "Cassandra",
        "description": "Read Cassandra cluster metadata and import node IP addresses to ipocket.",
        "kind": "Node inventory import",
        "help": "For full mapping/options, see /docs/cassandra-connector.md.",
        "command": "python -m app.connectors.cassandra --contact-points 10.0.0.10,10.0.0.11 --port 9042 --mode dry-run",
        "fields": [
            _field("contact_points", "Contact points", required=True, placeholder="10.0.0.10,10.0.0.11", span=True),
            _field("port", "Port", "number", required=True, default="9042", minimum=1, maximum=65535),
            _field("username", "Username (optional)", placeholder="cassandra"),
            _field("password", "Password (optional)", "password", placeholder="********", secret=True),
            ASSET_TYPE_FIELD,
            _field("project_name", "Project name (optional)", placeholder="Core"),
            _field("tags", "Tags (optional)", placeholder="cassandra,nodes"),
            _field("note", "Note (optional)", placeholder="Imported from Cassandra nodes", span=True),
            _field("use_tls", "Use TLS", "checkbox", default=False),
            _field("insecure", "Disable TLS verification", "checkbox", default=False),
            _field("include_cluster_name_tag", "Add cluster name as tag", "checkbox", default=False, span=True),
            TIMEOUT_FIELD,
            MODE_FIELD,
        ],
    },
    "ceph": {
        "display_name": "Ceph",
        "description": "Read Ceph Dashboard host inventory and import host IP addresses to ipocket.",
        "kind": "Host inventory import",
        "help": "For full mapping/options, see /docs/ceph-connector.md.",
        "command": "python -m app.connectors.ceph --ceph-url https://ceph-mgr.example.local:8443 --username admin --password '<password>' --mode dry-run",
        "fields": [
            _field("ceph_url", "Ceph Dashboard URL", "url", required=True, placeholder="https://ceph-mgr.example.local:8443", span=True),
            _field("username", "Username", required=True, placeholder="admin"),
            _field("password", "Password", "password", required=True, placeholder="********", secret=True),
            ASSET_TYPE_FIELD,
            _field("project_name", "Project name (optional)", placeholder="Storage"),
            _field("tags", "Tags (optional)", placeholder="ceph,nodes"),
            _field("note", "Note (optional)", placeholder="Imported from Ceph Dashboard hosts", span=True),
            _field("insecure", "Disable TLS verification", "checkbox", default=False),
            _field("include_cluster_name_tag", "Add cluster name as tag", "checkbox", default=False),
            _field("include_label_tags", "Add Ceph labels as tags", "checkbox", default=False, span=True),
            TIMEOUT_FIELD,
            MODE_FIELD,
        ],
    },
    "kubernetes": {
        "display_name": "Kubernetes",
        "description": "Read Kubernetes node InternalIP inventory and import node IP addresses to ipocket.",
        "kind": "Node inventory import",
        "help": "For full mapping/options, see /docs/kubernetes-connector.md.",
        "command": "python -m app.connectors.kubernetes --api-url https://kubernetes.example.local:6443 --token '<service-account-token>' --mode dry-run",
        "fields": [
            _field("api_url", "Kubernetes API URL", "url", required=True, placeholder="https://kubernetes.default.svc", span=True),
            _field("token", "Bearer token", "password", required=True, placeholder="ServiceAccount token", secret=True, span=True),
            {**ASSET_TYPE_FIELD, "default": "OS"},
            _field("project_name", "Project name (optional)", placeholder="Platform"),
            _field("tags", "Tags (optional)", placeholder="kubernetes,nodes"),
            _field("cluster_name", "Cluster name (optional)", placeholder="prod-cluster"),
            _field("note", "Note (optional)", placeholder="Imported from Kubernetes node InternalIP inventory", span=True),
            _field("insecure", "Disable TLS verification", "checkbox", default=False),
            _field("include_cluster_name_tag", "Add cluster name as tag", "checkbox", default=False),
            _field("include_label_tags", "Add Kubernetes node labels as tags", "checkbox", default=False, span=True),
            TIMEOUT_FIELD,
            MODE_FIELD,
        ],
    },
}


def safe_form_state(values: dict[str, object]) -> dict[str, object]:
    return {
        key: ("" if key.lower() in SECRET_FIELDS else value)
        for key, value in values.items()
        if key.lower() not in {"authorization", "headers"}
    }


def _text(payload: dict[str, Any], name: str, default: str = "") -> str:
    value = payload.get(name, default)
    return str(value).strip() if value is not None else default


def _bool(payload: dict[str, Any], name: str) -> bool:
    return payload.get(name) in {True, 1, "1", "true", "on", "yes"}


def _integer(
    payload: dict[str, Any], name: str, default: int, errors: list[str], message: str, *, maximum: int | None = None
) -> int:
    try:
        value = int(_text(payload, name, str(default)))
        if value <= 0 or (maximum is not None and value > maximum):
            raise ValueError
        return value
    except ValueError:
        errors.append(message)
        return default


def parse_connector_run(connector: str, payload: dict[str, Any]) -> tuple[ParsedConnectorRun | None, list[str]]:
    if connector not in CONNECTOR_SCHEMAS:
        return None, ["Unknown connector."]
    errors: list[str] = []
    mode = _text(payload, "mode", "dry-run").lower()
    if mode not in {"dry-run", "apply"}:
        errors.append("Mode must be dry-run or apply.")
    normalized_mode = mode if mode in {"dry-run", "apply"} else "dry-run"

    schema_fields = CONNECTOR_SCHEMAS[connector]["fields"]
    state: dict[str, object] = {}
    for field in schema_fields:  # type: ignore[assignment]
        name = str(field["name"])
        if field["type"] == "checkbox":
            state[name] = _bool(payload, name)
        else:
            state[name] = _text(payload, name, str(field.get("default", "")))
    state["mode"] = normalized_mode

    required_messages = {
        ("vcenter", "server"): "vCenter server is required.",
        ("vcenter", "username"): "vCenter username is required.",
        ("vcenter", "password"): "vCenter password is required.",
        ("prometheus", "prometheus_url"): "Prometheus URL is required.",
        ("prometheus", "query"): "PromQL query is required.",
        ("prometheus", "ip_label"): "IP label is required.",
        ("elasticsearch", "elasticsearch_url"): "Elasticsearch URL is required.",
        ("ceph", "ceph_url"): "Ceph Dashboard URL is required.",
        ("ceph", "username"): "Ceph username is required.",
        ("ceph", "password"): "Ceph password is required.",
        ("kubernetes", "api_url"): "Kubernetes API URL is required.",
        ("kubernetes", "token"): "Kubernetes bearer token is required.",
    }
    for field in schema_fields:  # type: ignore[assignment]
        name = str(field["name"])
        if field.get("required") and field["type"] not in {"number", "select"} and not _text(payload, name):
            message = required_messages.get((connector, name))
            if message:
                errors.append(message)

    kwargs: dict[str, object] = {}
    if connector == "vcenter":
        port = _integer(payload, "port", 443, errors, "Port must be a valid number between 1 and 65535.", maximum=65535)
        state["port"] = str(port)
        kwargs = {"server": state["server"], "username": state["username"], "password": _text(payload, "password"), "port": port, "insecure": state["insecure"], "mode": normalized_mode}
    else:
        timeout = _integer(payload, "timeout", 30, errors, "Timeout must be a positive integer.")
        state["timeout"] = str(timeout)
        asset_default = IPAssetType.OS.value if connector == "kubernetes" else IPAssetType.OTHER.value
        try:
            asset_type = IPAssetType.normalize(_text(payload, "asset_type", asset_default)).value
        except ValueError:
            errors.append("Asset type must be one of OS, BMC, VM, VIP, OTHER.")
            asset_type = asset_default
        state["asset_type"] = asset_type
        kwargs = {
            "asset_type": asset_type,
            "project_name": _text(payload, "project_name") or None,
            "tags": split_tag_string(_text(payload, "tags")) if _text(payload, "tags") else None,
            "timeout": timeout,
            "mode": normalized_mode,
        }

    if connector == "prometheus":
        kwargs.update(prometheus_url=state["prometheus_url"], query=state["query"], ip_label=state["ip_label"], token=_text(payload, "token") or None, insecure=state["insecure"])
    elif connector == "elasticsearch":
        username, password, api_key = _text(payload, "username"), _text(payload, "password"), _text(payload, "api_key")
        if api_key and (username or password): errors.append("Provide either API key or username/password authentication, not both.")
        elif username and not password: errors.append("Password is required when username is provided.")
        elif password and not username: errors.append("Username is required when password is provided.")
        kwargs.update(elasticsearch_url=state["elasticsearch_url"], username=username or None, password=password or None, api_key=api_key or None, note=_text(payload, "note") or None, include_cluster_name_tag=state["include_cluster_name_tag"])
    elif connector == "cassandra":
        try:
            points = parse_contact_points(_text(payload, "contact_points"))
        except CassandraConnectorError as exc:
            errors.append(str(exc)); points = []
        port = _integer(payload, "port", 9042, errors, "Port must be a valid number between 1 and 65535.", maximum=65535)
        state["port"] = str(port)
        username, password = _text(payload, "username"), _text(payload, "password")
        if username and not password: errors.append("Password is required when username is provided.")
        elif password and not username: errors.append("Username is required when password is provided.")
        if state["insecure"] and not state["use_tls"]: errors.append("Insecure TLS requires TLS to be enabled.")
        kwargs.update(contact_points=points, port=port, username=username or None, password=password or None, use_tls=state["use_tls"], insecure=state["insecure"], note=_text(payload, "note") or None, include_cluster_name_tag=state["include_cluster_name_tag"])
    elif connector == "ceph":
        kwargs.update(ceph_url=state["ceph_url"], username=state["username"], password=_text(payload, "password"), insecure=state["insecure"], note=_text(payload, "note") or None, include_cluster_name_tag=state["include_cluster_name_tag"], include_label_tags=state["include_label_tags"])
    elif connector == "kubernetes":
        kwargs.update(api_url=state["api_url"], token=_text(payload, "token"), insecure=state["insecure"], note=_text(payload, "note") or None, cluster_name=_text(payload, "cluster_name") or None, include_cluster_name_tag=state["include_cluster_name_tag"], include_label_tags=state["include_label_tags"])

    return ParsedConnectorRun(safe_form_state(state), kwargs, normalized_mode), errors
