# Export & Import Compatibility

ipocket supports exporting data for round-trip import later (import not yet implemented). Export endpoints are authenticated and default to excluding archived IP assets.

## Endpoints

Per-entity downloads (CSV + JSON):

- `GET /export/ip-assets.csv`
- `GET /export/ip-assets.json`
- `GET /export/hosts.csv`
- `GET /export/hosts.json`
- `GET /export/vendors.csv`
- `GET /export/vendors.json`
- `GET /export/projects.csv`
- `GET /export/projects.json`

Bundle downloads:

- `GET /export/bundle.json`
- `GET /export/bundle.zip` (bundle.json + per-entity CSVs)

### Query parameters

Applies where relevant:

- `include_archived=1` (include archived IP assets; default excludes archived)
- `type=OS|BMC|VM|VIP|OTHER` (IP assets only)
- `project=<name>` (IP assets + projects)
- `host=<name>` (IP assets + hosts)

## CSV formats

All CSV exports include a header row. Relationships are represented by name.

### ip-assets.csv

Columns:

- `ip_address`
- `subnet`
- `gateway`
- `type`
- `project_name`
- `host_name`
- `notes`
- `archived`
- `created_at`
- `updated_at`

### hosts.csv

Columns:

- `name`
- `notes`
- `vendor_name`

### vendors.csv

Columns:

- `name`

### projects.csv

Columns:

- `name`
- `description`

## JSON formats (per-entity)

Each JSON endpoint returns an array of objects with the same fields as the CSV columns.

### Example: /export/ip-assets.json

```json
[
  {
    "ip_address": "10.0.0.10",
    "subnet": "10.0.0.0/24",
    "gateway": "10.0.0.1",
    "type": "VM",
    "project_name": "core",
    "host_name": "node-01",
    "notes": "prod workload",
    "archived": false,
    "created_at": "2024-01-01 10:00:00",
    "updated_at": "2024-01-02 11:00:00"
  }
]
```

## Bundle JSON format (versioned)

`/export/bundle.json` returns:

```json
{
  "app": "ipocket",
  "schema_version": "1",
  "exported_at": "2024-01-01T12:00:00+00:00",
  "data": {
    "vendors": [...],
    "projects": [...],
    "hosts": [...],
    "ip_assets": [...]
  }
}
```

Each list uses the same per-entity JSON format described above. Use `schema_version` when building future importers.

## Authentication

Exports require authentication (UI session). Log in at `/ui/login` before accessing export endpoints.
