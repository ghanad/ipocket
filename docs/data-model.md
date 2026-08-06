# Data model

## IPAsset

- `ip_address` (unique)
- `ip_int` (nullable IPv4 integer used for database sorting/range filters)
- `project_id` (nullable)
- `type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`)
- `host_id` (nullable)
- `notes` (nullable)
- `archived` (soft-delete flag)
- timestamps (`created_at`, `updated_at`)
- Tags through `ip_asset_tags`

Creating an address that exists only as archived restores and updates that row.
Creating an already-active address returns a duplicate conflict. Clearing Notes,
Project, or Host stores a null/empty assignment and is audited like other
changes.

Exports are ordered by numeric IPv4 value. Legacy rows with a null `ip_int` use
parsed-address fallback ordering.

## Project

- `name` (unique)
- `description` (nullable)
- `color` (hex, default `#94a3b8`)

Deleting a Project sets linked IP assets' `project_id` to null before removing
the Project.

## Host

- `name` (unique)
- `notes` (nullable)
- `vendor_id` (nullable foreign key to Vendor)

OS and BMC assets are paired by sharing a Host. Host detail groups active linked
assets for presentation; Hosts do not store separate address or Tag fields.
Deleting a Host clears linked assets' `host_id` values and preserves the assets.
UI deletion requires acknowledgement and the exact Host name.

When enabled, creating a BMC asset without a Host creates or reuses a Host named
`server_<ip_address>` and assigns it. An explicit Host assignment takes
precedence. Set `IPOCKET_AUTO_HOST_FOR_BMC=0|false|no|off` to disable this
behavior and the matching detail-page action.

Host Completion uses the runtime `HOST_NAME_TEMPLATE` setting (default
`server_{bmc}`) as a naming aid; it does not add a stored Host column. A name
matching the template can deterministically identify an active, unlinked BMC
address for review.

## Vendor

- `name` (unique)

Deleting a Vendor clears matching `hosts.vendor_id` values before removing the
Vendor.

## Tag and IPAssetTag

Tag:

- `name` (unique, normalized to lowercase after trimming)
- `color` (hex, default `#e2e8f0`)
- timestamps

Names must match `^[a-z0-9_-]+$`. Assignment flows select existing Tags; new
Tags are created in Library. Deleting a Tag removes its relationship rows.

`IPAssetTag` contains `ip_asset_id` and `tag_id` with a unique constraint on the
pair. IP Assets list filtering supports OR (`tag_any`), AND (`tag_all`), and NOT
(`tag_not`); repeated legacy `tag` values are treated as OR.

## IPRange

- `name`
- `cidr` (unique IPv4 CIDR)
- `notes` (nullable)
- timestamps

Range membership and used/free utilization are derived from the CIDR and current
IP assets; individual address rows are not stored separately for free space.

## User

- `username` (unique)
- `hashed_password` (bcrypt; legacy SHA-256 upgraded after successful login)
- `role` (`Viewer`, `Editor`, or `Admin`, where Admin is Superuser)
- `is_active`

## Session

- `id`
- `token` (unique)
- `user_id` (foreign key to User, cascade delete)
- `created_at`

UI cookies and API bearer tokens resolve through the same persistent session
table. Login transports do not create alternate token stores.

## AuditLog

- `user_id` (nullable foreign key)
- `username` (snapshot retained after user deletion)
- `target_type` (`IP_ASSET`, `USER`, `IMPORT_RUN`, and related types)
- `target_id`
- `target_label`
- `action` (`CREATE`, `UPDATE`, `DELETE`, `APPLY`)
- `changes`
- `created_at`

Deleting a User sets historical logs' `user_id` to null while preserving the
username snapshot. Successful import/connector Apply runs create an `IMPORT_RUN`
record with `target_id=0` and a compact result summary; dry-runs do not.

## HostCompletionDecision

- `case_type` identifies a pairing, unlinked asset, or missing-side case
- `host_id` (nullable foreign key to Host, cascade delete)
- `mode` (`SUGGEST` or `ASK`)
- `os_address` and `bmc_address` (nullable case identity fields)
- `candidate_ip` (nullable)
- `corrected_ip` (nullable)
- `decision` (`ACCEPT`, `REJECT`, `CORRECTED`, `UNSURE`, `NO_BMC`, `NO_OS`,
  `CREATE_HOST_ONLY`, `ATTACH_EXISTING`, or `DEACTIVATE`)
- `target_host_id` and `host_name` (nullable decision context)
- `decided_by` (nullable foreign key to User; set null when the User is deleted)
- `created_at`

Decisions are immutable feedback events. Rules and their support,
contradictions, rejection counts, and confidence are recomputed from current
Host/IPAsset relationships plus these events; inferred rules are not stored.
`NO_BMC` and `NO_OS` exclude a Host from the matching missing-side queue.
Rejections remain Host/asset/candidate-specific and contribute contradictions
to derived rules. `UNSURE` is retained as feedback but can return later.

## Assignment workflow

Project assignment is managed from the main IP Assets list. **Project
Assignment** supports All, Assigned only, and Unassigned only; there is no
separate Needs Assignment page. Bulk edit can preserve, overwrite, or clear
Notes and can change Project, Type, and Tags for selected assets.

Host list filters and displayed IP Tags are derived from linked active IP assets
and do not create Host-level relationships.

## Imports and connectors

Bundle, CSV, Nmap, Prometheus, vCenter, Elasticsearch, Cassandra, Ceph, and
Kubernetes ingestion reuse the existing Vendor, Project, Host, IPAsset, Tag, and
AuditLog models. They do not add connector-specific tables.

Connector output controls update semantics:

- Prometheus preserves existing non-empty Notes and existing Type.
- vCenter preserves non-empty Notes, merges Tags, and may update Type.
- Elasticsearch and Cassandra merge Tags and may update Type/Project; Notes
  change only when a connector note is supplied.
- Ceph and Kubernetes additionally create/update Hosts and may update Host links,
  Type, and Project; optional cluster/label values become normalized Tags.

Host Completion cases, examples, analytics, and review candidates are
projections of active Host/IPAsset relationships. Analytics
classifies Hosts from their linked active OS/BMC assets; an `unlinked` Host has
neither type linked. Active assets without a Host still contribute to IP type
counts but cannot form confirmed pairs.

The Host Completion analytics UI at `/host-completion/analytics` reads this
projection on page load and when the operator retries a failed request. The
deterministic review engine persists decisions only; it does not persist
inferred patterns. The Editor-only
`/host-completion/review` UI submits `ACCEPT`, `REJECT`, `CORRECTED`, `UNSURE`,
and `NO_BMC` decisions against one queue item at a time, then reloads the
projection to select the next eligible Host.
