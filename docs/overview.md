# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors/admins)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- Needs Assignment UI for project-only assignment
- IP assets list supports HTMX-powered live search and filtering (including an assignment dropdown) without full page reloads.
- IP assets list includes an archived-only filter for reviewing soft-deleted records when needed.
- IP assets list includes pagination with a user-selectable page size (default 20) to keep large inventories manageable.
- IP list UI uses a compact three-dot actions menu per row to reduce clutter and separate safe actions from destructive actions.
- IP assets list includes a Host Pair column to show the OS or BMC IP linked to the same host.
- Deleting an IP from the list is now two-step: open row actions, confirm intent in a warning dialog, then complete deletion on the existing confirmation page (type exact IP).
- Tags on IP assets (comma-separated in the UI) for lightweight grouping, with a dedicated Tags page to manage names and colors.
- Management overview dashboard with quick totals for IPs, hosts, vendors, and projects, with cards linking to the relevant detail lists.
- CIDR-based subnet utilization report on the Management overview page that shows used vs. free IPs per range.
- IP ranges page supports editing and deleting saved CIDR ranges for cleanup, with a confirmation step that requires typing the exact range name.
- Range addresses view aligns columns with the IP assets list (plus Status), including Host Pair and Notes for used IPs in subnet drill-downs.
- Range addresses view includes an inline quick-add action to create IP assets directly from free entries without leaving the list.
- Export data as CSV, JSON, or bundle (JSON/ZIP) for round-trip workflows.
- Import data from bundle.json or CSV with dry-run support and upserts.
- Upload Nmap XML from the Import page to discover reachable IPs and add them as `OTHER` assets, with inline example commands.
- Prometheus metrics on `/metrics`
- Prometheus SD endpoint on `/sd/node` with project grouping
- Audit logging for IP asset create/update/delete actions, surfaced on the IP detail page and a global Audit Log view.
- Database schema managed through Alembic migrations

## Note
Owner support has been removed in development phase, so assignment is now project-only.


## Hosts

Hosts can be linked to a vendor from the shared **Vendors** catalog.

- Hosts list supports inline edit for name, vendor, and notes.
- Hosts list supports quick-add OS IP entry from the inline edit row for faster assignment (hidden once an OS IP is already linked).
- Hosts list uses the same three-dot actions menu pattern for edit/delete to keep the table compact.
- Hosts list shows linked OS and BMC IP addresses alongside the total linked IP count.
- Hosts list displays a project badge (with project color) based on linked IP assignments; multiple linked projects show a warning badge.
- Hosts page includes a collapsible search panel to filter by host name, vendor, notes, or linked IPs.
- Add Host form appears in a compact, collapsible card above the hosts table for quick entry in large inventories.
- Host deletion from UI is a two-step safety flow: open delete page, then type exact host name to confirm permanent deletion.

## Vendors

Vendors are managed as a dedicated list (create/edit) and are selectable when creating or editing Hosts (API and UI).
