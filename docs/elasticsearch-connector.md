# Elasticsearch connector (node inventory IP import)

ipocket includes an Elasticsearch connector that reads cluster node inventory from
`/_nodes/http,transport`, extracts IPv4 addresses, and imports those addresses
through the standard bundle import pipeline.

## Input model

Required inputs:
- `elasticsearch_url` (example: `https://127.0.0.1:9200`)
- Authentication:
  - `api_key` (Base64 string or `id:key`)
  - or `username` + `password`
- `asset_type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`; default `OTHER`)
- `mode` (`dry-run` or `apply` in UI; `file`/`dry-run`/`apply` in CLI)

Optional inputs:
- `project_name`
- `tags` (comma-separated)
- `note` (fixed text; when provided it overwrites existing note on update)
- `timeout` (default `30`)

TLS behavior:
- TLS certificate verification is always disabled for this connector (no toggle).

## UI usage

1. Open **Connectors → Elasticsearch**.
2. Fill URL and authentication (`API key` or `username/password`).
3. Set optional mapping fields (`type/project/tags/note`).
4. Run **dry-run** first and review execution log.
5. Run **apply** as an editor account.

## CLI usage

### File mode (bundle output only)

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --api-key '<base64-or-id:key>' \
  --asset-type OTHER \
  --mode file \
  --output ./elasticsearch-bundle.json
```

### Direct dry-run into local ipocket DB

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --username elastic \
  --password '<password>' \
  --tags elasticsearch,nodes \
  --mode dry-run \
  --db-path ./ipocket.db
```

### Direct apply into local ipocket DB

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --api-key '<base64-or-id:key>' \
  --project-name Core \
  --note 'Imported from Elasticsearch nodes' \
  --mode apply \
  --db-path ./ipocket.db
```

## IP extraction rules

For each node (`nodes.*`), the connector checks candidates in this order:
1. `http.publish_address`
2. `transport.publish_address`
3. `ip`
4. `host`

It accepts plain IP and `host:port` formats (including bracketed forms like
`[2001:db8::1]:9300`).

Behavior:
- Only IPv4 is imported.
- IPv6, loopback, invalid, and duplicate IPs are skipped with warnings.

## Mapping rules

Each extracted IPv4 becomes one `ip_assets` entry:
- `ip_address`: extracted IPv4
- `type`: selected/default asset type
- `project_name`: included only when provided
- `tags`: included only when provided
- `merge_tags`: `true` (append to existing tags on update)
- `notes`: included only when provided
- `notes_provided`: `true` only when `note` is provided
- `archived`: `false`

Update semantics for existing IPs:
- `type` is overwritten from connector input.
- `project` is overwritten when `project_name` is provided.
- tags are appended (merged).
- when `note` is provided, existing note is overwritten.
- when `note` is omitted, existing note is preserved.

## Failure behavior

Hard failures (`ElasticsearchConnectorError`):
- HTTP/auth/timeout/connection errors
- invalid JSON response
- missing/invalid `nodes` object

Soft issues (warnings, run continues):
- invalid/missing node IP candidates
- loopback/IPv6 addresses
- duplicate IPs in the same run
