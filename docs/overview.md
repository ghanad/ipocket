# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors/admins)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- Needs Assignment UI for project-only assignment
- IP list UI uses a compact three-dot actions menu per row to reduce clutter and separate safe actions from destructive actions.
- Deleting an IP from the list is now two-step: open row actions, confirm intent in a warning dialog, then complete deletion on the existing confirmation page (type exact IP).
- Export data as CSV, JSON, or bundle (JSON/ZIP) for round-trip workflows.
- Import data from bundle.json or CSV with dry-run support and upserts.
- Prometheus metrics on `/metrics`
- Prometheus SD endpoint on `/sd/node` with project grouping
- Audit logging for IP asset create/update/delete actions, surfaced on the IP detail page and a global Audit Log view.
- Database schema managed through Alembic migrations

## Note
Owner support has been removed in development phase, so assignment is now project-only.


## Hosts

Hosts can be linked to a vendor from the shared **Vendors** catalog.

- Hosts list supports inline edit for name, vendor, and notes.
- Hosts list uses the same three-dot actions menu pattern for edit/delete to keep the table compact.
- Hosts list shows linked OS and BMC IP addresses alongside the total linked IP count.
- Add Host form appears in a compact card above the hosts table for quick entry in large inventories.
- Host deletion from UI is a two-step safety flow: open delete page, then type exact host name to confirm permanent deletion.

## Vendors

Vendors are managed as a dedicated list (create/edit) and are selectable when creating or editing Hosts (API and UI).
