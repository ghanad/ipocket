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

## Project
- `name` (unique)
- `description` (optional)
- `color` (hex color, default `#94a3b8`)

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


## IPAssetTag
- `ip_asset_id` (FK to `ip_assets.id`)
- `tag_id` (FK to `tags.id`)
- unique (`ip_asset_id`, `tag_id`)


## BMC auto-host linkage
- On create (both REST API and UI form), when an IPAsset has `type=BMC` and `host_id` is omitted/null, ipocket auto-links it to a Host named exactly `server_{ip_address}`.
- If that Host already exists, it is reused (no duplicate Host creation).
- If `host_id` is provided explicitly, no auto-host creation is performed.


## Host
- `name` (TEXT, unique)
- `notes` (TEXT, nullable)
- `vendor_id` (INTEGER, nullable; FK to `vendors.id`)


## Vendor
- `name` (TEXT, unique)

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
- `target_label` stores the run source (for example `api_import_bundle`, `ui_import_csv`, `connector_vcenter`, `connector_prometheus`).
- `changes` stores a compact text summary including input type and create/update/skip/warnings/errors counts.


## Host deletion rule
- Host permanent delete is allowed only when no IP assets are linked to it.
- UI delete requires typing the exact host name as confirmation (two-step flow).

## Assignment workflow
- Project assignment is managed from the main **IP Assets** list using filters and edit actions.
- There is no separate "Needs Assignment" page in the current UI.
- Range address drill-down (`/ui/ranges/{id}/addresses`) now adds UI-only search/status/pagination controls; this does not change persisted schema or entity fields.

## Connector ingestion note
- Prometheus and vCenter connectors do not introduce new database tables or fields.
- Connector runs generate standard import bundles (`schema_version=1`) and upsert through the existing IPAsset import pipeline.
- UI connector runs execute as background jobs so long-running remote calls do not block a single web request.
- Upserts only change optional fields when those values are explicitly included in connector output; Prometheus updates keep existing `type`, while vCenter updates can overwrite `type`.
- Prometheus connector entries set `preserve_existing_notes=true`, so non-empty manual notes on existing IP assets are not overwritten during upsert.
- Prometheus connector entries also set `preserve_existing_type=true`, so existing IP records keep their current `type` during update while new records still use the connector-selected `type`.
- Prometheus connector UI dry-run now renders per-IP change previews (`CREATE`/`UPDATE`/`SKIP`) with field-level differences before apply.
- vCenter connector entries set `preserve_existing_notes=true` and `merge_tags=true`; this keeps non-empty manual notes, merges connector tags with existing tags, and still updates the connector-provided `type`.
