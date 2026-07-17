# Cassandra connector (node metadata IP import)

## React UI

Open `/ui/connectors?tab=cassandra`. The shared form preserves contact-point, port, authentication, TLS, and insecure-TLS validation. Viewers can dry-run; Editors can Apply after confirmation. Background polling does not reload the page, credentials are not retained, and the legacy form POST remains compatible.

ipocket includes a Cassandra connector that connects through the Python
`cassandra-driver`, reads cluster metadata, extracts node IPv4 addresses, and
imports those addresses through the standard bundle import pipeline.

## Input model

Required inputs:
- `contact_points` (comma-separated, example: `10.0.0.10,10.0.0.11`)
- `asset_type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`; default `OTHER`)
- `mode` (`dry-run` or `apply` in UI; `file`/`dry-run`/`apply` in CLI)

Optional inputs:
- `port` (default `9042`)
- Authentication: `username` + `password`
- `use_tls`
- `insecure` (only valid when TLS is enabled; disables certificate verification)
- `project_name`
- `tags` (comma-separated)
- `note` (fixed text; when provided it overwrites existing note on update)
- `include_cluster_name_tag` / `--include-cluster-name-tag` (off by default)
- `timeout` (default `30`)

## UI usage

1. Open **Connectors → Cassandra**.
2. Fill contact points and port. Authentication and TLS are optional.
3. Set optional mapping fields (`type/project/tags/note`).
4. Optionally check **Add cluster name as tag** to tag every imported node IP
   with the Cassandra metadata `cluster_name`.
5. Run **dry-run** first and review the execution log. React polls the background job
   while the run is queued/running.
6. Run **apply** as an editor account.

## CLI usage

### File mode (bundle output only)

```bash
python -m app.connectors.cassandra \
  --contact-points 10.0.0.10,10.0.0.11 \
  --port 9042 \
  --asset-type OTHER \
  --mode file \
  --output ./cassandra-bundle.json
```

### Direct dry-run into local ipocket DB

```bash
python -m app.connectors.cassandra \
  --contact-points 10.0.0.10,10.0.0.11 \
  --username cassandra \
  --password '<password>' \
  --use-tls \
  --insecure \
  --tags cassandra,nodes \
  --include-cluster-name-tag \
  --mode dry-run \
  --db-path ./ipocket.db
```

### Direct apply into local ipocket DB

```bash
python -m app.connectors.cassandra \
  --contact-points cassandra-a.example.local,cassandra-b.example.local \
  --project-name Core \
  --note 'Imported from Cassandra nodes' \
  --mode apply \
  --db-path ./ipocket.db
```

## IP extraction rules

The connector reads `cluster.metadata.all_hosts()` from the Cassandra driver and
uses each host metadata object's `address`.

Behavior:
- Only IPv4 is imported.
- IPv6, loopback, invalid, empty, and duplicate IPs are skipped with warnings.
- Node inventory is read from driver metadata, not from `system.peers`.

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
- when cluster-name tagging is enabled, the Cassandra `cluster_name` is
  normalized and appended to `tags` for every imported IP.
- when `note` is provided, existing note is overwritten.
- when `note` is omitted, existing note is preserved.

Cluster tag normalization:
- The raw `cluster_name` is trimmed and lowercased.
- Characters outside `a-z`, `0-9`, dash, and underscore become `-`.
- Repeated dashes collapse and leading/trailing dashes are removed.
- Example: `Prod.Cassandra 01` becomes `prod-cassandra-01`.
- If the value is missing or normalizes to empty, the connector skips the
  cluster tag and records a warning; node IP import still continues.

## Failure behavior

Hard failures (`CassandraConnectorError`):
- missing `cassandra-driver` dependency
- authentication/timeout/connection errors
- Cassandra metadata read failures

Soft issues (warnings, run continues):
- invalid/missing node addresses
- loopback/IPv6 addresses
- duplicate IPs in the same run
