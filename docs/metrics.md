# Metrics

ipocket exposes Prometheus text metrics at `GET /metrics`.

## Required counters

- `ipam_ip_total`: all IP asset rows, including archived rows.
- `ipam_ip_archived_total`: archived IP asset rows.
- `ipam_ip_unassigned_project_total`: active IP assets without a Project.
- `ipam_ip_unassigned_owner_total`: active IP assets without an Owner; currently
  `0` while Owner support is paused.
- `ipam_ip_unassigned_both_total`: active IP assets without both Owner and
  Project; currently `0` while Owner support is paused.

Re-creating an address that exists only as archived restores the existing row,
so one record moves from archived to active instead of increasing the total.

Use **IP Assets → Project Assignment → Unassigned only** to review the records
represented by `ipam_ip_unassigned_project_total`. There is no dedicated Needs
Assignment page.

## Scope

The endpoint intentionally reports inventory counters only. UI filters,
catalogs, authentication, Host Completion reads, exports, and connector jobs do
not add exporter-side metric names. Applied imports and connectors affect these
counters only through their normal IP asset creates, updates, restores, and
archives.

Host completion statistics and deterministic review data are JSON, not
Prometheus series. Reading analytics or the review queue does not mutate
inventory or change the counters above. `ACCEPT`, `CORRECTED`,
`ATTACH_EXISTING`, and `DEACTIVATE` decisions can create, restore, update,
link, or archive an IP asset through the normal audited mutation path,
so the existing inventory counters reflect those changes without adding new
metric names.

The `/host-completion/analytics` page visualizes the same JSON. Page views and
manual reloads do not create exporter-side metrics.
The `/host-completion/review` page also adds no metrics of its own; accepted or
corrected BMC links affect only the existing inventory counters.
Its Host-name template and autocomplete are UI/API workflow metadata only and
do not create Prometheus series.
