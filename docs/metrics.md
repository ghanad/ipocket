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
