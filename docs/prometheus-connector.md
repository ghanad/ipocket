# Prometheus connector (query-driven IP import)

ipocket includes a Prometheus connector that reads vector query results from
`/api/v1/query`, extracts IPv4 addresses from a selected label, and imports
those addresses through the existing bundle import pipeline.

## Typical use case

For node_exporter, many setups expose targets with `instance="<ip>:9100"`.
You can query those metrics and add matching IPs to ipocket.

## Input model

Required inputs:
- `prometheus_url` (example: `http://127.0.0.1:9090`)
- `query` (PromQL expression)
- `ip_label` (label containing IP or `host:port`, commonly `instance`)

Optional inputs:
- `asset_type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`; default `OTHER`)
- `project_name`
- `tags` (comma-separated)
- Prometheus auth (either Bearer token or `username:password`)
- TLS skip (`insecure`)

## UI usage

1. Open **Connectors → Prometheus**.
2. Set URL/query/label and optional mapping fields.
3. Run **dry-run** first.
4. Review execution log and warnings (dry-run includes extracted IP preview, per-IP `CREATE`/`UPDATE`/`SKIP` details with field-level diffs, and `ip_assets` create/update/skip summary).
5. Run **apply** as an editor account.

## CLI usage

### File mode (bundle output only)

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --asset-type OTHER \
  --mode file \
  --output ./prometheus-bundle.json
```

### Direct dry-run into ipocket API

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --token 'prom_user:prom_pass' \
  --mode dry-run \
  --ipocket-url http://127.0.0.1:8000 \
  --ipocket-token '<token>'
```

### Direct apply into ipocket API

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --mode apply \
  --ipocket-url http://127.0.0.1:8000 \
  --ipocket-token '<token>'
```

Auth note:
- `--token abc123` sends `Authorization: Bearer abc123`
- `--token 'username:password'` sends HTTP Basic Auth

## Mapping rules

Each extracted IPv4 becomes one bundle `ip_assets` entry:
- `ip_address`: parsed IPv4
- `type`: selected/default asset type
- `project_name`: included only when provided
- `tags`: included only when provided
- `notes`: generated from query context for traceability
- `preserve_existing_notes`: `true` (keep non-empty existing notes on update)
- `preserve_existing_type`: `true` (keep existing type on update)
- `archived`: `false`

Connector behavior:
- Deduplicates repeated IPs in one run.
- Skips invalid IP/IPv6 values with warnings.
- Skips loopback IPs (`127.0.0.0/8`) with warnings.
- Skips samples where the selected label is missing.
- Accepts `host:port` and extracts the host part.
- UI dry-run logs include per-IP action details so you can review exactly which fields would be created or changed before apply.

## Failure behavior

Hard failures (`PrometheusConnectorError`):
- Prometheus API HTTP/auth/TLS/timeout errors
- Invalid JSON from API
- response status other than `success`
- unsupported `resultType` (must be `vector`)

Soft issues (warnings, run continues):
- label missing on some samples
- invalid label value for IPv4 extraction
- duplicate IP inside one run

## Import semantics

The connector sends data to the standard import engine, so behavior matches other
bundle imports:
- New IPs are created.
- Existing IPs are updated only when connector output explicitly includes a value
  for optional fields (project/tags/notes/type).
- Prometheus connector updates do not overwrite non-empty existing IP notes; those
  notes stay unchanged while other provided fields can still be updated.
- Prometheus connector updates keep the current IP `type` for existing records,
  even when connector input contains a different `asset_type`. New records still
  use the selected/default connector `asset_type`.
- No new schema/table is introduced.
