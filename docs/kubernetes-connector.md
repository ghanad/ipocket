# Kubernetes connector (Node InternalIP import)

ipocket includes a Kubernetes connector that uses the Kubernetes REST API to
read Node inventory, create/update matching ipocket Hosts, and link imported
Node `InternalIP` IPv4 addresses to those Hosts.

The connector calls:
- `GET /api/v1/nodes` with `Authorization: Bearer <token>`.

## Input model

Required inputs:
- `api_url` / `--api-url` (Kubernetes API base URL, example:
  `https://kubernetes.example.local:6443`)
- `token` / `--token` (bearer token with permission to list nodes)
- `asset_type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`; default `OS`)
- `mode` (`dry-run` or `apply` in UI; `file`/`dry-run`/`apply` in CLI)

Optional inputs:
- `insecure` / `--insecure` (disable TLS certificate verification)
- `project_name`
- `tags` (comma-separated)
- `note` (fixed text; when provided it overwrites existing IP note on update)
- `cluster_name` / `--cluster-name`
- `include_cluster_name_tag` / `--include-cluster-name-tag`
- `include_label_tags` / `--include-label-tags`
- `timeout` (default `30`)

## UI usage

1. Open **Connectors → Kubernetes**.
2. Fill the Kubernetes API URL and bearer token.
3. Set optional mapping fields (`type/project/tags/note`).
4. Optionally add a normalized cluster name or Kubernetes node labels as tags.
5. Run **dry-run** first and review the execution log. The tab auto-refreshes
   while the run is queued/running.
6. Run **apply** as an editor account.

## CLI usage

### File mode (bundle output only)

```bash
python -m app.connectors.kubernetes \
  --api-url https://kubernetes.example.local:6443 \
  --token '<service-account-token>' \
  --asset-type OS \
  --mode file \
  --output ./kubernetes-bundle.json
```

### Direct dry-run into local ipocket DB

```bash
python -m app.connectors.kubernetes \
  --api-url https://kubernetes.example.local:6443 \
  --token '<service-account-token>' \
  --tags kubernetes,nodes \
  --include-label-tags \
  --mode dry-run \
  --db-path ./ipocket.db
```

### Direct apply into local ipocket DB

```bash
python -m app.connectors.kubernetes \
  --api-url https://kubernetes.example.local:6443 \
  --token '<service-account-token>' \
  --project-name Platform \
  --cluster-name prod-cluster \
  --include-cluster-name-tag \
  --note 'Imported from Kubernetes node inventory' \
  --mode apply \
  --db-path ./ipocket.db
```

## IP extraction rules

The connector reads Kubernetes Nodes and uses `status.addresses` entries where
`type` is `InternalIP`.

Behavior:
- Only IPv4 `InternalIP` addresses are imported.
- IPv6, loopback, invalid, empty, and duplicate IPs are skipped with warnings.
- Host records are created/updated by Kubernetes Node `metadata.name`.
- Imported IP assets are linked to the matching Host through `host_name`.
- Pods, Services, ExternalIP, and LoadBalancer IPs are intentionally out of
  scope for this connector version.

## Mapping rules

Each valid Kubernetes Node becomes:
- one `hosts` entry with `name` set to Node `metadata.name`
- one `ip_assets` entry per valid Node `InternalIP`, linked by `host_name`

Each extracted IPv4 asset includes:
- `ip_address`: Node `InternalIP`
- `type`: selected/default asset type
- `host_name`: Kubernetes Node name
- `project_name`: included only when provided
- `tags`: included only when provided or generated from cluster/labels
- `merge_tags`: `true` (append to existing tags on update)
- `notes`: included only when provided
- `notes_provided`: `true` only when `note` is provided
- `archived`: `false`

Update semantics for existing IPs:
- `type` is overwritten from connector input.
- `project` is overwritten when `project_name` is provided.
- `host` is updated to the imported Kubernetes node Host.
- tags are appended (merged).
- when `note` is provided, existing note is overwritten.
- when `note` is omitted, existing note is preserved.

## Failure behavior

Hard failures (`KubernetesConnectorError`):
- HTTP/auth/TLS/timeout failures
- invalid JSON responses
- unexpected NodeList payload shape

Soft issues (warnings, run continues):
- missing Node names
- missing `InternalIP` addresses
- loopback/IPv6 addresses
- invalid IP values
- duplicate IPs in the same run
