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

Host reconciliation statistics and deterministic findings are authenticated
JSON, not Prometheus series. Reading the summary or finding queue does not
mutate inventory. Superuser-managed manual mappings affect the JSON findings
but add no Prometheus metric. `ACCEPT`, `CORRECT`, `ATTACH_EXISTING`, and `DEACTIVATE`
decisions can create a Host, link assets, or archive an asset through one
audited transaction. `CORRECT` may also create the operator-supplied OS/BMC
counterpart asset when it is not yet in inventory, so existing counters reflect
the result without
adding new metric names.

The `/host-completion/analytics` and `/host-completion/review` pages add no
metrics of their own. Rule support, contradictions, reconciliation states, and
the unexplained-assets KPI are available from the JSON summary only.
