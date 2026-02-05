# Service Discovery (Prometheus HTTP SD)

ipocket exposes a Prometheus-compatible HTTP service discovery endpoint:

- `GET /sd/node`

The response is a JSON array of target groups (`targets` + `labels`) and is compatible with `http_sd_configs`.

## Query parameters

- `port` (optional, default `9100`): node-exporter port appended to each target.
- `only_assigned` (optional, default `0`): when `1`/`true`, exclude IPs missing either Owner or Project.
- `project` (optional, multi-value): include only IPs with matching project names.
  - Multi-value is supported by comma-separated values (`?project=omid,payments`) or repeated params (`?project=omid&project=payments`).
- `owner` (optional, multi-value): include only IPs with matching owner names.
  - Multi-value is supported by comma-separated values (`?owner=ali,reza`) or repeated params (`?owner=ali&owner=reza`).
- `type` (optional, multi-value): include only matching asset types (`VM`, `PHYSICAL`, `IPMI_ILO`, `VIP`, `OTHER`).
  - Use repeated params (`?type=VM&type=VIP`).
- `group_by` (optional, default `none`): controls how targets are split into target groups.
  - `none`: one target group containing all matching targets.
  - `project`: one target group per project label.
  - `owner`: one target group per owner label.
  - `project_owner`: one target group per `(project, owner)` pair.

## Inclusion rules and labels

- Only **non-archived** IP assets are returned.
- Labels always include:
  - `project`
  - `owner`
  - `type`
- Missing owner/project values are returned as `"unassigned"`.
- When a grouped target set contains mixed values for a label, that group label is set to `"multiple"`.

## URL examples

- `/sd/node`
- `/sd/node?project=omid`
- `/sd/node?owner=ali`
- `/sd/node?project=omid&owner=reza`
- `/sd/node?project=omid,payments&only_assigned=1`
- `/sd/node?type=VM&type=VIP&group_by=project_owner`

## Response examples

### `group_by=none` (default)

```json
[
  {
    "targets": ["10.20.0.1:9100", "10.20.0.2:9100"],
    "labels": {
      "project": "multiple",
      "owner": "multiple",
      "type": "multiple"
    }
  }
]
```

### `group_by=project`

```json
[
  {
    "targets": ["10.20.0.1:9100", "10.20.0.2:9100"],
    "labels": {
      "project": "omid",
      "owner": "multiple",
      "type": "multiple"
    }
  },
  {
    "targets": ["10.20.0.3:9100"],
    "labels": {
      "project": "unassigned",
      "owner": "unassigned",
      "type": "OTHER"
    }
  }
]
```

### `group_by=project_owner`

```json
[
  {
    "targets": ["10.20.0.1:9100"],
    "labels": {
      "project": "omid",
      "owner": "ali",
      "type": "VM"
    }
  },
  {
    "targets": ["10.20.0.2:9100"],
    "labels": {
      "project": "omid",
      "owner": "reza",
      "type": "PHYSICAL"
    }
  }
]
```

## Prometheus configuration examples

### Basic scrape using all targets

```yaml
scrape_configs:
  - job_name: node-exporters
    http_sd_configs:
      - url: http://127.0.0.1:8000/sd/node
        refresh_interval: 30s
```

### Scrape only assigned targets for specific projects

```yaml
scrape_configs:
  - job_name: node-exporters-assigned
    http_sd_configs:
      - url: http://127.0.0.1:8000/sd/node?project=omid,payments&only_assigned=1
        refresh_interval: 30s
```

### Split scrapes by project-owner group

```yaml
scrape_configs:
  - job_name: node-exporters-grouped
    http_sd_configs:
      - url: http://127.0.0.1:8000/sd/node?group_by=project_owner&port=9100
        refresh_interval: 30s
```

## Security

The endpoint is intended for internal monitoring networks.

Optional token auth is supported:

- Set `IPOCKET_SD_TOKEN` in ipocket environment.
- Send `X-SD-Token` header from Prometheus.

Prometheus supports request headers via `http_headers`:

```yaml
scrape_configs:
  - job_name: node-exporters
    http_sd_configs:
      - url: http://127.0.0.1:8000/sd/node
        refresh_interval: 30s
        http_headers:
          X-SD-Token:
            values: ["sd-secret-token"]
```

If `IPOCKET_SD_TOKEN` is not set, `/sd/node` does not require authentication.
