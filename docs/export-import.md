# Export & Import

ipocket supports round-trip workflows: export data (CSV/JSON/bundle) and re-import it later. Imports are modular and use a parser → validator → applier pipeline so future sources (like nmap output) can be added without rewriting core logic.

## Import endpoints

### API

- `POST /import/bundle?dry_run=1`
  - Multipart form upload with field: `file` (bundle.json).
- `POST /import/csv?dry_run=1`
  - Multipart form upload with fields: `hosts` (hosts.csv) and `ip_assets` (ip-assets.csv).

### UI

Open `/ui/import` and upload:

- Bundle JSON section: `bundle.json`
- CSV section: `hosts.csv` + `ip-assets.csv`

Dry-run runs validation and returns a summary without writing to the database. Apply performs upserts.

## Permissions

- Viewer: allowed to Dry-run.
- Editor/Admin: allowed to Apply.

## Bundle JSON schema

```json
{
  "app": "ipocket",
  "schema_version": "1",
  "exported_at": "2024-01-01T12:00:00+00:00",
  "data": {
    "vendors": [{"name": "HPE"}],
    "projects": [{"name": "Core", "description": "", "color": "#94a3b8"}],
    "hosts": [{"name": "node-01", "notes": "", "vendor_name": "HPE"}],
    "ip_assets": [
      {
        "ip_address": "10.0.0.10",
        "subnet": "10.0.0.0/24",
        "gateway": "10.0.0.1",
        "type": "VM",
        "project_name": "Core",
        "host_name": "node-01",
        "notes": "",
        "archived": false
      }
    ]
  }
}
```

`schema_version` must be `1`.

## CSV formats

The CSV import expects the same columns as the CSV exports.

### hosts.csv

Columns:

- `name` (required)
- `notes`
- `vendor_name`

### ip-assets.csv

Columns:

- `ip_address` (required)
- `subnet`
- `gateway`
- `type` (required: `OS`, `BMC`, `VM`, `VIP`, `OTHER`)
- `project_name`
- `host_name`
- `notes`
- `archived`

## Dry-run behavior

Dry-run validates records, returns row-level errors with line numbers (CSV) or object paths (bundle JSON), and reports what would be created/updated/skipped. No database writes occur.

## Import pipeline (extensible)

Imports are split into three steps:

1. **Importer/Parser**: Converts input files into an `ImportBundle` structure (vendors/projects/hosts/ip_assets).
2. **Validator**: Checks required fields, reference integrity, IP formatting, and allowed types.
3. **Applier**: Upserts entities in a safe order (vendors/projects → hosts → ip_assets).

To add a future importer (e.g., nmap), implement the importer interface (`parse(...) -> ImportBundle`) and reuse the validator + applier.
