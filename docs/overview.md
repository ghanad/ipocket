# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors/admins)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- IP assets list supports HTMX-powered live search and filtering (including an assignment dropdown) without full page reloads.
- Project assignment review is handled directly in the IP Assets list via the **Assignment** filter (`Unassigned only`); the dedicated Needs Assignment page has been removed.
- IP assets search results are sorted by numeric IP value (so `192.168.1.2` appears before `192.168.1.11`) instead of plain text ordering.
- IP assets list supports one-click filtering from table values: clicking a Project/Type chip applies that filter instantly, and Tag filtering now uses an autocomplete textbox with multi-tag ANY matching.
- IP assets list includes an archived-only filter for reviewing soft-deleted records when needed.
- IP assets list includes pagination with a user-selectable page size (default 20) to keep large inventories manageable.
- IP assets list uses a right-side drawer for both adding and editing IPs without leaving the list view.
- Saving an IP edit from the drawer returns to the list view instead of navigating to the detail page.
- Creating an IP from the drawer now also returns to the list view (preserving active filters/query state) instead of navigating to a detail URL.
- After saving in the drawer, the list view restores the prior scroll position.
- Host assignment in the drawer only appears when the IP type is OS or BMC.
- BMC IPs without a host assignment show a drawer action to create and assign a host named `server_<ip>`.
- IP assets list includes a Host Pair column to show the OS or BMC IP linked to the same host.
- IP assets list shows inline Edit/Delete actions side-by-side in the Actions column.
- Deleting an IP from the list now uses the same right-side drawer shell as Add/Edit but with strict modes: delete mode hides all edit inputs, shows a compact destructive confirmation summary (IP/Project/Type/Host), keeps the acknowledgement checkbox inline with its label, and for high-risk assets requires typing the exact IP before “Delete permanently” is enabled.
- IP asset detail page now uses the shared card/chip visual language, including metadata chips in the header, a key-value Details card, badge-styled audit actions with optional raw detail expansion, and in-page delete via the same right-side delete drawer mode used on the list view.
- IP assets list includes bulk edit controls to update type, project assignment, or add tags across multiple IPs at once.
- Tags on IP assets (comma-separated in the UI) for lightweight grouping, with a dedicated Tags page to manage names and colors.
- Tag deletion from the Tags page now requires a browser confirmation prompt before the delete request is submitted.
- Management overview dashboard with quick totals for IPs, hosts, vendors, and projects, with cards linking to the relevant detail lists.
- CIDR-based subnet utilization report on the Management overview page that shows used vs. free IPs per range.
- Sidebar remains fixed-height with its own scroll to keep navigation and account actions accessible on long pages.
- The old fixed top header has been removed from the main layout to give pages more vertical space; branding remains in the left sidebar.
- UI templates now keep behavior and page-specific styling in static assets (`app/static/js/*.js` and `app/static/app.css`) to keep Jinja markup focused on structure.
- The sidebar account section shows Login when signed out and Logout when signed in.
- IP ranges page supports editing and deleting saved CIDR ranges for cleanup, with a confirmation step that requires typing the exact range name.
- Saved ranges now use the same inline Edit/Delete button style as Hosts so table actions stay visually consistent across pages.
- Range addresses view aligns columns with the IP assets list (plus Status), including Host Pair and Notes for used IPs in subnet drill-downs.
- Range addresses view now uses a right-side drawer for both “Add” (free IPs) and “Edit” (used IPs), matching the IP assets page workflow.
- IP ranges page now opens “Add IP Range” inside a right-side drawer instead of an inline card, keeping create UX consistent with Hosts/IP assets flows.
- IP ranges page now opens range editing in a right-side drawer too, so Edit keeps users on `/ui/ranges` like Hosts and IP assets.
- IP ranges page now performs delete confirmation inside a matching right-side drawer (with explicit acknowledgement + exact-name typing) so destructive actions follow the same interaction pattern as IP asset delete.
- Range delete drawer now reliably displays CIDR/usage context from the selected row (including when opened inline), reducing confirmation mistakes.
- IP ranges now render in a single unified table card (name/CIDR/usable/used/free/utilization/actions), with Used/Free counts staying clickable for address drill-down and row-level Edit/Delete actions kept compact.
- Drawer open/close behavior is shared through `app/static/js/drawer.js` so Hosts and Ranges follow the same interaction pattern.
- Projects page now follows the same right-side drawer UX as Ranges for create/edit/delete actions, including destructive confirmation by typing the exact project name.
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
- Host deletion from UI is a two-step safety flow: open delete page, then type exact host name to confirm permanent deletion; Cancel returns to host detail page and successful deletion shows a flash message (consistent with IP asset delete flow).

## Vendors

Vendors are managed as a dedicated list (create/edit) and are selectable when creating or editing Hosts (API and UI).

- UI route handlers are now organized as a modular package under `app/routes/ui/` (`auth.py`, `dashboard.py`, `ip_assets.py`, `hosts.py`, `ranges.py`, `settings.py`, `data_ops.py`) with shared helpers in `utils.py` and a single aggregated `router` exported from `app/routes/ui/__init__.py`.
- Developer compatibility note: `app/routes/ui/__init__.py` re-exports UI auth/session helpers (including `SESSION_COOKIE`) so existing integrations and tests continue working after modularization.

- API route handlers are now organized as a modular package under `app/routes/api/` (`auth.py`, `system.py`, `assets.py`, `hosts.py`, `metadata.py`, `imports.py`) with shared schemas/dependencies/helpers and a single aggregated `router` exported from `app/routes/api/__init__.py`.
- Developer compatibility note: `app/routes/api/__init__.py` re-exports auth dependency helpers (`get_current_user`, `require_editor`) for stable imports during the refactor.
