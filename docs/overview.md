# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors/admins)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- Needs Assignment UI for project-only assignment
- IP assets list supports HTMX-powered live search and filtering (including an assignment dropdown) without full page reloads.
- IP assets search results are sorted by numeric IP value (so `192.168.1.2` appears before `192.168.1.11`) instead of plain text ordering.
- IP assets list supports one-click filtering from table values: clicking a Project/Type chip applies that filter instantly, and Tag filtering now uses an autocomplete textbox with multi-tag ANY matching.
- IP assets list includes an archived-only filter for reviewing soft-deleted records when needed.
- IP assets list includes pagination with a user-selectable page size (default 20) to keep large inventories manageable.
- IP assets list uses a right-side drawer for both adding and editing IPs without leaving the list view.
- Saving an IP edit from the drawer returns to the list view instead of navigating to the detail page.
- After saving in the drawer, the list view restores the prior scroll position.
- Host assignment in the drawer only appears when the IP type is OS or BMC.
- BMC IPs without a host assignment show a drawer action to create and assign a host named `server_<ip>`.
- IP assets list includes a Host Pair column to show the OS or BMC IP linked to the same host.
- IP assets list shows inline Edit/Delete actions side-by-side in the Actions column.
- Deleting an IP from the list is now two-step: open the delete dialog, confirm intent in a warning dialog, then complete deletion on the existing confirmation page (type exact IP).
- IP assets list includes bulk edit controls to update type, project assignment, or add tags across multiple IPs at once.
- Tags on IP assets (comma-separated in the UI) for lightweight grouping, with a dedicated Tags page to manage names and colors.
- Tag deletion from the Tags page now requires a browser confirmation prompt before the delete request is submitted.
- Management overview dashboard with quick totals for IPs, hosts, vendors, and projects, with cards linking to the relevant detail lists.
- CIDR-based subnet utilization report on the Management overview page that shows used vs. free IPs per range.
- Sidebar remains fixed-height with its own scroll to keep navigation and account actions accessible on long pages.
- UI templates now keep behavior and page-specific styling in static assets (`app/static/js/*.js` and `app/static/app.css`) to keep Jinja markup focused on structure.
- The sidebar account section shows Login when signed out and Logout when signed in.
- IP ranges page supports editing and deleting saved CIDR ranges for cleanup, with a confirmation step that requires typing the exact range name.
- Range addresses view aligns columns with the IP assets list (plus Status), including Host Pair and Notes for used IPs in subnet drill-downs.
- Range addresses view now uses a right-side drawer for both “Add” (free IPs) and “Edit” (used IPs), matching the IP assets page workflow.
- IP ranges page now opens “Add IP Range” inside a right-side drawer instead of an inline card, keeping create UX consistent with Hosts/IP assets flows.
- Drawer open/close behavior is shared through `app/static/js/drawer.js` so Hosts and Ranges follow the same interaction pattern.
- Export data as CSV, JSON, or bundle (JSON/ZIP) for round-trip workflows.
- Import data from bundle.json or CSV with dry-run support and upserts.
- Upload Nmap XML from the Import page to discover reachable IPs and add them as `OTHER` assets, with inline example commands.
- Prometheus metrics on `/metrics`
- Prometheus SD endpoint on `/sd/node` with project grouping
- Audit logging for IP asset create/update/delete actions, surfaced on the IP detail page and a global Audit Log view (both require authentication).
- Database schema managed through Alembic migrations
- Repository data-access layer is modularized under `app/repository/` (assets, hosts, ranges, metadata, users, audit, summary), while `app.repository` remains the stable import surface via package re-exports.

## Note
Owner support has been removed in development phase, so assignment is now project-only.


## Hosts

Hosts can be linked to a vendor from the shared **Vendors** catalog.

- Hosts list uses a right-side edit drawer for name, vendor, notes, single-value OS/BMC IP updates, and project/status context (with inline IPv4 validation); changing project updates linked IP assignments.
- Host add form still supports inline OS and BMC IP address inputs so linked addresses can be captured during host creation.
- Hosts list shows side-by-side Edit/Delete actions in the Actions column for quick access.
- Hosts list shows linked OS and BMC IP addresses alongside the total linked IP count.
- Hosts list displays a project badge (with project color) based on linked IP assignments; multiple linked projects show a warning badge.
- Hosts page includes a collapsible search panel to filter by host name, vendor, notes, or linked IPs.
- Adding a host now uses the same right-side drawer interaction as editing, so create/edit actions stay visually consistent.
- Host deletion from UI is a two-step safety flow: open delete page, then type exact host name to confirm permanent deletion.

## Vendors

Vendors are managed as a dedicated list (create/edit) and are selectable when creating or editing Hosts (API and UI).

- UI route handlers are now organized as a modular package under `app/routes/ui/` (`auth.py`, `dashboard.py`, `ip_assets.py`, `hosts.py`, `ranges.py`, `settings.py`, `data_ops.py`) with shared helpers in `utils.py` and a single aggregated `router` exported from `app/routes/ui/__init__.py`.
- Developer compatibility note: `app/routes/ui/__init__.py` re-exports UI auth/session helpers (including `SESSION_COOKIE`) so existing integrations and tests continue working after modularization.

- API route handlers are now organized as a modular package under `app/routes/api/` (`auth.py`, `system.py`, `assets.py`, `hosts.py`, `metadata.py`, `imports.py`) with shared schemas/dependencies/helpers and a single aggregated `router` exported from `app/routes/api/__init__.py`.
- Developer compatibility note: `app/routes/api/__init__.py` re-exports auth dependency helpers (`get_current_user`, `require_editor`) for stable imports during the refactor.
