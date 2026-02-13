# Export & Import

ipocket supports round-trip workflows: export data (CSV/JSON/bundle) and re-import it later. Imports are modular and use a parser → validator → applier pipeline so future sources (like nmap output) can be added without rewriting core logic.

## Import endpoints

### API

- `POST /import/bundle?dry_run=1`
  - Multipart form upload with field: `file` (bundle.json).
- `POST /import/csv?dry_run=1`
  - Multipart form upload with fields: `hosts` (hosts.csv) and/or `ip_assets` (ip-assets.csv). Empty files are ignored.

### UI

Open `/ui/import` and use the tabs:

- `Import` tab for uploads
- `Export` tab for downloads (bundle plus per-entity IP Assets/Hosts links)

The Export tab uses the same responsive multi-card layout pattern as Import.

On the `Import` tab upload:

- Bundle JSON section: `bundle.json`
- CSV section: `hosts.csv` and/or `ip-assets.csv` (empty uploads are ignored)
- Nmap XML section: `ipocket.xml` from your Nmap scan

The Import tab renders these three sections as equal-sized cards in a responsive grid (3 columns on wide screens, then 2 and 1 on smaller screens).
Each card keeps a dedicated action footer so `Dry-run`/`Apply` stay aligned at the bottom of the card.

Sample CSVs are available for download on the import page (or directly via `/static/samples/hosts.csv` and
`/static/samples/ip-assets.csv`) to illustrate the required columns and formatting.

Dry-run runs validation and returns a summary without writing to the database. Apply performs upserts.
All three import sections (Bundle, CSV, Nmap XML) use the same `Dry-run` and `Apply` button pattern in the UI.

## Permissions

- Viewer: allowed to Dry-run.
- Editor: allowed to Apply.

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
        "type": "VM",
        "project_name": "Core",
        "host_name": "node-01",
        "tags": ["prod", "edge"],
        "notes": "",
        "archived": false
      }
    ]
  }
}
```

`schema_version` must be `1`.

## CSV formats

The CSV import expects the same columns as the CSV exports, plus optional columns noted below.

### hosts.csv

Columns:

- `name` (required)
- `notes`
- `vendor_name`
- `project_name` (optional project to assign to `os_ip`/`bmc_ip` assets)
- `os_ip` (optional OS IP to create an `OS` IP asset linked to the host)
- `bmc_ip` (optional BMC IP to create a `BMC` IP asset linked to the host)

### ip-assets.csv

Columns:

- `ip_address` (required)
- `type` (required: `OS`, `BMC`, `VM`, `VIP`, `OTHER`)
- `project_name`
- `host_name`
- `tags` (comma-separated tag names)
- `notes`
- `archived`

Tag values are normalized (trimmed + lowercased). Allowed characters are letters, digits, dashes, and underscores.
For `ip-assets.csv`, leaving `notes` empty clears an existing note on import (it is treated as an explicit update).

## Dry-run behavior

Dry-run validates records, returns row-level errors with line numbers (CSV) or object paths (bundle JSON), and reports what would be created/updated/skipped. No database writes occur.

## Import pipeline (extensible)

Imports are split into three steps:

1. **Importer/Parser**: Converts input files into an `ImportBundle` structure (vendors/projects/hosts/ip_assets).
2. **Validator**: Checks required fields, reference integrity, IP formatting, and allowed types.
3. **Applier**: Upserts entities in a safe order (vendors/projects → hosts → ip_assets).

To add a future importer (e.g., nmap), implement the importer interface (`parse(...) -> ImportBundle`) and reuse the validator + applier.
