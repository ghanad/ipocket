# Service Discovery (Prometheus HTTP SD)

ipocket exposes a Prometheus-compatible HTTP service discovery endpoint:

- `GET /sd/node`

The response is a JSON array of target groups (`targets` + `labels`) and is compatible with `http_sd_configs`.

## Query parameters

- `port` (optional, default `9100`): node-exporter port appended to each target.
- `only_assigned` (optional, default `0`): when `1`/`true`, exclude IPs missing either Owner or Project.
- `project` (optional): include only IPs where project name matches exactly.

## Inclusion rules

- Only **non-archived** IP assets are returned.
- Labels always include:
  - `project`
  - `owner`
  - `type`
- Missing owner/project values are returned as `"unassigned"`.

## Response format example

```json
[
  {
    "targets": ["10.20.0.1:9100"],
    "labels": {
      "project": "Core",
      "owner": "NetOps",
      "type": "VM"
    }
  },
  {
    "targets": ["10.20.0.2:9100"],
    "labels": {
      "project": "Core",
      "owner": "unassigned",
      "type": "PHYSICAL"
    }
  }
]
```

## Prometheus configuration example

```yaml
scrape_configs:
  - job_name: node-exporters
    http_sd_configs:
      - url: http://127.0.0.1:8000/sd/node?port=9100&only_assigned=1
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
