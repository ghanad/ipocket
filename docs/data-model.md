# Data model

## IPAsset
- `ip_address` (unique)
- `project_id` (optional)
- `type` (`VM`, `OS`, `BMC`, `VIP`, `OTHER`)
- `host_id` (optional)
- `notes` (optional; clearing the field removes the stored note and is recorded in the audit log)
- `archived` (soft delete)
- tags (many-to-many via `ip_asset_tags`)
- timestamps (`created_at`, `updated_at`)

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


## AuditLog
- `user_id` (INTEGER, nullable; FK to `users.id`)
- `username` (TEXT, nullable snapshot of username at action time)
- `target_type` (TEXT, ex: `IP_ASSET`)
- `target_id` (INTEGER)
- `target_label` (TEXT, ex: IP address)
- `action` (TEXT, `CREATE`, `UPDATE`, `DELETE`)
- `changes` (TEXT summary of changes; no-op updates are skipped)
- `created_at` (TEXT timestamp)


## Host deletion rule
- Host permanent delete is allowed only when no IP assets are linked to it.
- UI delete requires typing the exact host name as confirmation (two-step flow).
