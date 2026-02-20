# Metrics

The app exposes Prometheus metrics at `GET /metrics`:

- `ipam_ip_total`: total number of IP records (including archived).
- `ipam_ip_archived_total`: number of archived IP records.
- `ipam_ip_unassigned_project_total`: number of active IP records without a project assignment.
- `ipam_ip_unassigned_owner_total`: number of active IP records without an owner assignment (currently `0` while owner support is paused).
- `ipam_ip_unassigned_both_total`: number of active IP records without both owner and project assignments (currently `0` while owner support is paused).

Archived restore note:
- Re-creating an IP that currently exists only as archived restores that row (sets `archived=0`) rather than creating a duplicate row, so totals reflect a single record transitioning between archived/active states.


Note: Vendor catalog/host vendor selection does not introduce new Prometheus metrics in this release.

UI note: unassigned-related metrics are still available even though the dedicated **Needs Assignment** page was removed; use the IP Assets list filters for assignment workflows.
UI note: range-address search/status/pagination changes are presentation-only and do not affect `/metrics` payloads.

Connector note: connectors import through the same IP upsert pipeline (Prometheus preserves non-empty notes and existing `type` on update, and UI dry-run shows per-IP field-level change previews; vCenter overwrites type, merges connector tags, and only writes notes when existing notes are empty), but they do not add exporter-side Prometheus metrics in ipocket; `/metrics` remains limited to IP inventory counters listed above.

Account note: self-service password change (`/ui/account/password`) is a UI/audit behavior change only and does not add or alter `/metrics` counters.
Auth/session note: bcrypt password hashing and database-backed session tokens do not add or alter `/metrics` counters.
