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

Current Host reconciliation uses the fixed `server_<bmc-ip>` convention when it
creates or reuses a Host; it does not add a stored Host column. The legacy
prototype's name-derived suggestion path still recognizes
`HOST_NAME_TEMPLATE` for migration compatibility.

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

- `case_type` identifies `CREATE_HOST`, `COMPLETE_HOST`, `UNMATCHED_ASSET`, or
  `CONFLICT` (legacy prototype values may remain in older rows)
- `host_id` (nullable foreign key to Host, cascade delete)
- `mode` (`SUGGEST` or `ASK`)
- `os_address` and `bmc_address` (nullable case identity fields)
- `candidate_ip` (nullable)
- `corrected_ip` (nullable)
- `decision` includes `ACCEPT`, `CORRECT`, `WRONG_PAIR`, `UNSURE`, `EXCEPTION`,
  `ATTACH_EXISTING`, and `DEACTIVATE` (legacy values remain migration-compatible)
- `target_host_id` and `host_name` (nullable decision context)
- `proposal_id` and `inventory_fingerprint` bind the decision to a particular
  derived finding and inventory state
- `idempotency_key` (nullable unique retry key)
- `decided_by` (nullable foreign key to User; set null when the User is deleted)
- `created_at`

Decisions are immutable agent state, not authoritative inventory. Rules and
their support, contradictions, strength, and examples are recomputed from
current Host/IPAsset relationships plus explicit feedback. Only `WRONG_PAIR`
is negative mapping evidence; `UNSURE` and `EXCEPTION` are not contradictions.
The unique idempotency key prevents duplicate mutation events.

## HostCompletionManualRule

Superusers may persist an explicit OS-to-BMC IPv4 mapping with
`source_prefix`, `target_prefix`, a shared `prefix_length` (`16` or `24`),
`active`, optional `notes`, creator, and timestamps. An active manual rule is
treated as strong deterministic policy; it overrides an equivalent learned
rule. Deactivation retains the row and its `HOST_COMPLETION_RULE` audit entries
but removes it from proposal generation.

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

`ipocket_agent` does not define database models and never imports ipocket's
repositories. ipocket projects its current Hosts, active/archived IP Assets,
and minimal operator feedback into the agent. Findings and rules are derived on
demand; Hosts and IP Assets are never copied into an agent-owned database.

Every active OS/BMC asset is classified as `RESOLVED`, `PROPOSED`, `UNMATCHED`,
`CONFLICT`, or `EXCEPTION`. Reconciliation coverage is
`(RESOLVED + PROPOSED + EXCEPTION) / active OS/BMC assets`. The operational KPI
is `UNMATCHED + CONFLICT`, named **unexplained active assets**, with a goal of 0.

Manual reconciliation is address-driven. The operator supplies the missing OS
or BMC IP; the API resolves or creates that IP Asset, derives the Host name as
`server_<bmc-ip>`, and links both sides in the same transaction. Numeric Asset
and Host IDs are internal implementation details, not normal UI inputs.
