# Ceph connector (Dashboard host IP import)

ipocket includes a Ceph connector that uses the Ceph Dashboard REST API to read
host inventory, create/update matching ipocket Hosts, and link imported host
IPv4 addresses to those Hosts.

The connector calls:
- `POST /api/auth` to obtain a Dashboard JWT.
- `GET /api/host` to read host inventory.

## Input model

Required inputs:
- `ceph_url` / `--ceph-url` (Ceph Dashboard base URL, example:
  `https://ceph-mgr.example.local:8443`)
- `username`
- `password`
- `asset_type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`; default `OTHER`)
- `mode` (`dry-run` or `apply` in UI; `file`/`dry-run`/`apply` in CLI)

Optional inputs:
- `insecure` / `--insecure` (disable TLS certificate verification)
- `project_name`
- `tags` (comma-separated)
- `note` (fixed text; when provided it overwrites existing IP note on update)
- `include_cluster_name_tag` / `--include-cluster-name-tag`
- `include_label_tags` / `--include-label-tags`
- `timeout` (default `30`)

## UI usage

1. Open **Connectors → Ceph**.
2. Fill the Ceph Dashboard URL, username, and password.
3. Set optional mapping fields (`type/project/tags/note`).
4. Optionally add normalized cluster name or Ceph host labels as tags.
5. Run **dry-run** first and review the execution log. The tab auto-refreshes
   while the run is queued/running.
6. Run **apply** as an editor account.

## CLI usage

### File mode (bundle output only)

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --asset-type OTHER \
  --mode file \
  --output ./ceph-bundle.json
```

### Direct dry-run into local ipocket DB

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --insecure \
  --tags ceph,nodes \
  --include-label-tags \
  --mode dry-run \
  --db-path ./ipocket.db
```

### Direct apply into local ipocket DB

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --project-name Storage \
  --note 'Imported from Ceph Dashboard hosts' \
  --mode apply \
  --db-path ./ipocket.db
```

## IP extraction rules

The connector reads host records from the Dashboard host API and uses each
record's `addr` field.

Behavior:
- Only IPv4 is imported.
- IPv6, loopback, invalid, empty, and duplicate IPs are skipped with warnings.
- Host records are created/updated by Ceph `hostname`.
- Imported IP assets are linked to the matching Host through `host_name`.

## Mapping rules

Each valid Ceph host becomes:
- one `hosts` entry with `name` set to Ceph `hostname`
- one `ip_assets` entry linked by `host_name`

Each extracted IPv4 asset includes:
- `ip_address`: host `addr`
- `type`: selected/default asset type
- `host_name`: Ceph `hostname`
- `project_name`: included only when provided
- `tags`: included only when provided or generated from cluster/labels
- `merge_tags`: `true` (append to existing tags on update)
- `notes`: included only when provided
- `notes_provided`: `true` only when `note` is provided
- `archived`: `false`

Update semantics for existing IPs:
- `type` is overwritten from connector input.
- `project` is overwritten when `project_name` is provided.
- `host` is updated to the imported Ceph host.
- tags are appended (merged).
- when `note` is provided, existing note is overwritten.
- when `note` is omitted, existing note is preserved.

## Failure behavior

Hard failures (`CephConnectorError`):
- authentication failures or missing token
- HTTP/timeout/TLS failures
- invalid JSON responses
- unexpected host payload shape

Soft issues (warnings, run continues):
- invalid/missing host addresses
- loopback/IPv6 addresses
- duplicate IPs in the same run
