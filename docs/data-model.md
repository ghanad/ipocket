# Data model

## IPAsset
- `ip_address` (unique)
- `ip_int` (optional INTEGER; derived IPv4 numeric value used for SQL sorting/range filters, null for non-IPv4 values)
- `project_id` (optional)
- `type` (`VM`, `OS`, `BMC`, `VIP`, `OTHER`)
- `host_id` (optional)
- `notes` (optional; clearing the field removes the stored note and is recorded in the audit log)
- `archived` (soft delete)
- tags (many-to-many via `ip_asset_tags`)
- timestamps (`created_at`, `updated_at`)

Create behavior with archived records:
- If a create request uses an `ip_address` that exists only as an archived record, ipocket restores that same row (`archived=0`) and updates its fields instead of creating a second row.
- If the same `ip_address` already exists as an active record, create still fails with duplicate-address conflict.

Bulk edit note behavior:
- In **IP Assets → Bulk update**, notes are controlled via **Notes action** (`Keep current`, `Overwrite with value below`, `Clear all notes`).
- `Overwrite with value below` requires a non-empty note value.
- `Clear all notes` removes notes from all selected rows.

UI redirect behavior:
- IP Assets bulk/update/delete flows strip stale toast query parameters (`bulk-error`, `bulk-success`, `delete-error`, `delete-success`) before appending a new result message.
- Deleting an IP Asset from its detail page returns to `/ui/ip-assets`; this is a navigation/UI behavior only and does not change stored relationships.

Export ordering behavior:
- IP asset exports (`/export/ip-assets.csv`, `/export/ip-assets.json`, bundle payload) are ordered by numeric IPv4 value.
- When legacy rows have `ip_int` as null, export ordering falls back to parsing `ip_address` so numeric order is preserved.

## Project
- `name` (unique)
- `description` (optional)
- `color` (hex color, default `#94a3b8`)

Deleting a Project unassigns its linked IP assets (`project_id=NULL`) before
removing the catalog row. The React Library UI does not change this relationship
behavior.

## IPRange
- `name` (range label)
- `cidr` (IPv4 CIDR, unique)
- `notes` (optional)
- timestamps (`created_at`, `updated_at`)


## Tag
- `name` (unique, required)
- `color` (hex color, default `#e2e8f0`)
- timestamps (`created_at`, `updated_at`)

Tag names are normalized by trimming whitespace and lowercasing. Allowed characters are letters, digits, dashes, and
underscores (`^[a-z0-9_-]+$`).
UI assignment flows only allow selecting from existing tags; they do not create new tags during IP assignment.
IP Assets tag filtering is UI/query behavior only and does not change tag relationships. The list supports **OR** (`tag_any`), **AND** (`tag_all`), and **NOT** (`tag_not`) filter groups; legacy repeated `tag` query values are treated as **OR** filters for compatibility.
Deleting a Tag removes its `ip_asset_tags` relationship rows before deleting the
Tag. Library usage counts include active IP assets only.


## IPAssetTag
- `ip_asset_id` (FK to `ip_assets.id`)
- `tag_id` (FK to `tags.id`)
- unique (`ip_asset_id`, `tag_id`)


## BMC auto-host linkage
- On create (both REST API and UI form), when an IPAsset has `type=BMC` and `host_id` is omitted/null, ipocket auto-links it to a Host named exactly `server_{ip_address}`.
- If that Host already exists, it is reused (no duplicate Host creation).
- If `host_id` is provided explicitly, no auto-host creation is performed.


## OS/BMC host pairing
- OS and BMC IP assets are paired through their shared `host_id`.
- On an IP Asset detail page, OS records show linked BMC addresses for the same host, and BMC records show linked OS addresses for the same host. The IP address, Host, and paired OS/BMC address values are navigation links to the corresponding detail pages.
- Pair addresses are not shown for `VM`, `VIP`, or `OTHER` asset types.


## Host
- `name` (TEXT, unique)
- `notes` (TEXT, nullable)
- `vendor_id` (INTEGER, nullable; FK to `vendors.id`)

Host detail grouping is presentation-only: active linked IP assets are grouped as OS, BMC, and other asset types with their existing project, tag, and notes metadata without changing the stored Host or IPAsset relationships. The Hosts list also renders OS/BMC linked IPs as navigation links to existing IPAsset detail pages and shows deduplicated tags from linked active IP assets; when many tags exist, extra tags are collapsed in the UI only. This does not add host-level address or tag fields.

## Vendor
- `name` (TEXT, unique)

Deleting a Vendor clears matching `hosts.vendor_id` values before deleting the
Vendor. Vendor Library usage counts include active IP assets linked through
those Hosts.

## User
- `username` (TEXT, unique)
- `hashed_password` (TEXT; bcrypt hash via `passlib`, with legacy SHA-256 hashes upgraded on successful login)
- `role` (`Viewer`, `Editor`, `Admin` where `Admin` is treated as Superuser)
- `is_active` (INTEGER flag; `1` active, `0` inactive)


## Session
- `id` (INTEGER primary key)
- `token` (TEXT, unique)
- `user_id` (INTEGER, FK to `users.id`, cascade delete)
- `created_at` (TEXT timestamp)

API bearer tokens and UI login cookies both map to this table for session validation and revocation.


## AuditLog
- `user_id` (INTEGER, nullable; FK to `users.id`)
- `username` (TEXT, nullable snapshot of username at action time)
- `target_type` (TEXT, ex: `IP_ASSET`, `USER`, `IMPORT_RUN`)
- `target_id` (INTEGER)
- `target_label` (TEXT, ex: IP address)
- `action` (TEXT, `CREATE`, `UPDATE`, `DELETE`, `APPLY`)
- `changes` (TEXT summary of changes; no-op updates are skipped)
- `created_at` (TEXT timestamp)

When a user account is deleted, existing audit logs are preserved by setting `audit_logs.user_id` to `NULL` while keeping `username` snapshots intact.
Self-service password changes (`/ui/account/password`) do not add fields/tables; they write a standard `AuditLog` entry with `target_type=USER`, `action=UPDATE`, and a password-rotation change summary.

`IMPORT_RUN` convention:
- Recorded only for successful `apply` executions (not `dry-run`).
- Uses `target_id=0` as a run-level sentinel.
- `target_label` stores the run source (for example `api_import_bundle`, `ui_import_csv`, `connector_vcenter`, `connector_prometheus`, `connector_elasticsearch`).
- `changes` stores a compact text summary including input type and create/update/skip/warnings/errors counts.


## Host deletion rule
- Host permanent delete keeps linked IP assets and clears their `host_id` before
  removing the Host row.
- UI delete requires acknowledgement and typing the exact Host name.

## Assignment workflow
- Project assignment is managed from the main **IP Assets** list using filters and edit actions.
- There is no separate "Needs Assignment" page in the current UI.
- Range address drill-down (`/ui/ranges/{id}/addresses`) now adds UI-only search/status/pagination controls; this does not change persisted schema or entity fields.
- Migrating the `/ui/ranges` list to React changes only presentation and transport. The React page uses `/api/ui/ranges` for list/create/update/delete operations against the existing `IPRange` repository model; no columns, relationships, migrations, or utilization calculations were added.
- Migrating `/ui/projects` (Projects/Vendors/Tags) to React changes only presentation and transport. The focused `/api/ui/library/*` endpoints use the existing repository models and deletion rules; no tables, columns, relationships, or migrations were added.
- Migrating the `/ui/hosts` list to React changes only presentation and transport. The focused `/api/ui/hosts` endpoints reuse existing Host/IPAsset repository semantics; public GET access, role-gated mutations, and server-resolved legacy Drawer bootstrap do not add tables, columns, or relationships. `/ui/hosts/{id}` remains unchanged.
- Hosts list filtering by text, project, assignment, status, vendor, and tags is UI/query behavior only. React keeps filters and pagination in the query string, while legacy `edit`/`delete` targets are loaded independently so a valid Host does not depend on appearing in the current page. Host tag filters and the Hosts table **IP tags** column both use tags on linked active IP assets and do not add host-level tag storage; selected filter chips retain the catalog `--tag-color` and contrast text color. Compact tag-chip sizing, clicking tag chips to apply the existing tag filter, and collapsing extra tag chips behind `+N more` are presentation-only.

## Connector ingestion note
- Prometheus, vCenter, Elasticsearch, Cassandra, Ceph, and Kubernetes connectors do not introduce new database tables or fields.
- Connector runs generate standard import bundles (`schema_version=1`) and upsert through the existing IPAsset import pipeline.
- UI connector runs execute as background jobs so long-running remote calls do not block a single web request.
- Upserts only change optional fields when those values are explicitly included in connector output; Prometheus updates keep existing `type`, while vCenter updates can overwrite `type`.
- Prometheus connector entries set `preserve_existing_notes=true`, so non-empty manual notes on existing IP assets are not overwritten during upsert.
- Prometheus connector entries also set `preserve_existing_type=true`, so existing IP records keep their current `type` during update while new records still use the connector-selected `type`.
- Prometheus connector UI dry-run now renders per-IP change previews (`CREATE`/`UPDATE`/`SKIP`) with field-level differences before apply.
- vCenter connector entries set `preserve_existing_notes=true` and `merge_tags=true`; this keeps non-empty manual notes, merges connector tags with existing tags, and still updates the connector-provided `type`.
- Elasticsearch connector entries set `merge_tags=true` and do not set preserve flags; updates can overwrite `type` and `project` when provided, optionally append a normalized `cluster_name` tag when the connector option is enabled, and overwrite notes only when connector `note` is explicitly provided.
- Cassandra connector entries set `merge_tags=true` and do not set preserve flags; updates can overwrite `type` and `project` when provided, optionally append a normalized Cassandra `cluster_name` tag when the connector option is enabled, and overwrite notes only when connector `note` is explicitly provided.
- Ceph connector entries set `merge_tags=true` and do not set preserve flags; host records are created/updated from Ceph `hostname`, IP assets are linked to those hosts through `host_name`, updates can overwrite `type`, `project`, and `host` when provided, optionally append normalized cluster/label tags, and overwrite notes only when connector `note` is explicitly provided.
- Kubernetes connector entries set `merge_tags=true` and do not set preserve flags; host records are created/updated from Kubernetes Node `metadata.name`, IP assets are linked to those hosts through `host_name`, updates can overwrite `type`, `project`, and `host` when provided, optionally append normalized cluster/label tags, and overwrite notes only when connector `note` is explicitly provided.
