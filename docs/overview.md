# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors only)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- IP assets list supports HTMX-powered live search and filtering (including an assignment dropdown) without full page reloads.
- Project filter on IP assets now includes an `Unassigned` option to show only IPs without a project directly from the Project dropdown.
- Project assignment review is handled directly in the IP Assets list via the **Assignment** filter (`Unassigned only`); the dedicated Needs Assignment page has been removed.
- IP assets search results are sorted by numeric IP value (so `192.168.1.2` appears before `192.168.1.11`) instead of plain text ordering.
- IP assets list supports one-click filtering from table values: clicking a Project/Type chip applies that filter instantly, and Tag filtering now uses an autocomplete textbox with multi-tag ANY matching.
- Selected tags in the top Tags filter keep each tag's configured catalog color, including chips added live from the autocomplete input.
- IP assets list includes an archived-only filter for reviewing soft-deleted records when needed.
- IP assets list includes pagination with a user-selectable page size (default 20) to keep large inventories manageable.
- IP assets list rows use compact spacing for IP text and Project/Type chips to keep more records visible per page.
- IP assets table keeps `IP address`, `Project`, and `Type` columns narrow because their values are bounded, leaving more horizontal space for Tags and Notes.
- IP assets list uses a right-side drawer for both adding and editing IPs without leaving the list view.
- Saving an IP edit from the drawer returns to the list view instead of navigating to the detail page.
- Clearing Project in the IP edit drawer now correctly unassigns the IP (`project_id` becomes null) instead of keeping the previous project.
- Creating an IP from the drawer now also returns to the list view (preserving active filters/query state) instead of navigating to a detail URL.
- After saving in the drawer, the list view restores the prior scroll position.
- Host assignment in the drawer only appears when the IP type is OS or BMC.
- BMC IPs without a host assignment show a drawer action to create and assign a host named `server_<ip>`.
- IP assets list hides Host Pair to keep the table focused on assignment and editing fields.
- IP assets list shows inline Edit/Delete actions side-by-side in the Actions column.
- Deleting an IP from the list now uses the same right-side drawer shell as Add/Edit but with strict modes: delete mode hides all edit inputs, shows a compact destructive confirmation summary (IP/Project/Type/Host), keeps the acknowledgement checkbox inline with its label, and for high-risk assets requires typing the exact IP before “Delete permanently” is enabled.
- IP asset detail page now uses the shared card/chip visual language, including metadata chips in the header, a key-value Details card, badge-styled audit actions with optional raw detail expansion, and in-page delete via the same right-side delete drawer mode used on the list view.
- IP assets list includes bulk edit controls to update type, project assignment, or add tags across multiple IPs at once.
- IP assets list keeps tag cells compact: up to 3 chips are shown in-row, and extra tags move into a `+N more` popover (open on hover or click, with keyboard/outside-click close and inline tag search).
- IP assets list keeps Notes cells single-line to preserve row height; full note text appears in a hover/focus tooltip after a short pointer delay.
- IP assets table uses a fixed responsive layout so long Notes/Tags content does not force horizontal page scrolling.
- Tags on IP assets are now selected from existing Tag records (no free-text tag creation during assignment), with a dedicated Tags page to manage names and colors.
- Tag selection UI now uses a chip-based picker (`Add tags...`) with searchable dropdown suggestions, Enter/click add, chip remove (`×`), and Backspace removal of the last selected chip.
- Tag chips now auto-pick a high-contrast text color (dark/light) based on each tag background color across the IP edit/add drawers, IP assets table tags, and tag popovers.
- Tags page now uses the same right-side drawer pattern as Projects/Vendors for create/edit/delete, including destructive confirmation by typing the exact tag name. The tags table also shows an **IPs** count column with how many active IP assets currently use each tag.
- Tag create drawer suggests a random tag color by default (instead of one fixed color), and users can override it before saving.
- Management overview dashboard with quick totals for IPs, hosts, vendors, and projects, with cards linking to the relevant detail lists.
- CIDR-based subnet utilization report on the Management overview page that shows used vs. free IPs per range.
- Sidebar remains fixed-height with its own scroll to keep navigation and account actions accessible on long pages.
- The old fixed top header has been removed from the main layout to give pages more vertical space; branding remains in the left sidebar.
- UI templates now keep behavior and page-specific styling in static assets (`app/static/js/*.js` and `app/static/app.css`) to keep Jinja markup focused on structure.
- The sidebar account section shows Login when signed out and Logout when signed in.
- User access model now distinguishes `Editor` (data write) from `Superuser` (user management only); read routes stay public except audit log, which still requires authentication.
- User management is available on `/ui/users` (superuser-only) and writes user-management actions to audit logs with target type `USER`.
- The `/ui/users` page is visible and accessible only to authenticated superusers.
- User create/edit/delete on `/ui/users` uses the same right-side drawer pattern as other management pages.
- The sidebar footer shows build metadata (`version/commit/build time`) whenever the sidebar is visible, including signed-out views.
- IP ranges page supports editing and deleting saved CIDR ranges for cleanup, with a confirmation step that requires typing the exact range name.
- Saved ranges now use the same inline Edit/Delete button style as Hosts so table actions stay visually consistent across pages.
- Range addresses view includes Status, Host Pair, and Notes for used IPs in subnet drill-downs.
- Range addresses view now uses a right-side drawer for both “Add” (free IPs) and “Edit” (used IPs), matching the IP assets page workflow.
- IP ranges page now opens “Add IP Range” inside a right-side drawer instead of an inline card, keeping create UX consistent with Hosts/IP assets flows.
- IP ranges page now opens range editing in a right-side drawer too, so Edit keeps users on `/ui/ranges` like Hosts and IP assets.
- IP ranges page now performs delete confirmation inside a matching right-side drawer (with explicit acknowledgement + exact-name typing) so destructive actions follow the same interaction pattern as IP asset delete.
- Range delete drawer now reliably displays CIDR/usage context from the selected row (including when opened inline), reducing confirmation mistakes.
- IP ranges now render in a single unified table card (name/CIDR/usable/used/free/utilization/actions), with Used/Free counts staying clickable for address drill-down and row-level Edit/Delete actions kept compact.
- Drawer open/close behavior is shared through `app/static/js/drawer.js` so Hosts and Ranges follow the same interaction pattern.
- Projects management is part of the shared Library page and follows the same right-side drawer UX for create/edit/delete actions, including destructive confirmation by typing the exact project name.
- The Library page uses one shared "Catalog Settings" header with compact segmented tabs (Projects/Tags/Vendors) and a tab-aware primary action button (New Project/Tag/Vendor) to keep controls in one place.
- The Projects and Tags tab tables now use compact row spacing so catalog rows stay denser and easier to scan.
- Projects table now shows an **IPs** count column so you can quickly see how many active IP assets are currently assigned to each project.
- Use the shared **Data Ops** page (Import/Export tabs) for round-trip workflows.
- Export data as CSV, JSON, or bundle (JSON/ZIP) from the Data Ops Export tab.
- Import data from bundle.json or CSV with dry-run support and upserts from the Data Ops Import tab.
- Upload Nmap XML from the Data Ops Import tab to discover reachable IPs and add them as `OTHER` assets, with inline example commands.
- Sidebar now includes a **Connectors** page with tabs (`Overview` / `vCenter`) so operators can find connector status and run the vCenter connector from UI.
- **Connectors → vCenter** supports both `dry-run` and `apply` execution modes and shows an in-page execution log (inventory summary + warnings/errors) after each run.
- Manual vCenter connector is available via `python -m app.connectors.vcenter` (ESXi hosts as `OS` + tag `esxi`, VMs as `VM`) with both file export mode and direct API dry-run/apply modes.
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
- Host add form supports selecting a project plus inline OS/BMC IP inputs; when a project is selected, newly linked IP assets inherit that project during host creation.
- Hosts list shows side-by-side Edit/Delete actions in the Actions column for quick access.
- Hosts list shows linked OS and BMC IP addresses alongside the total linked IP count.
- In Host edit, clearing an OS/BMC IP from the drawer and saving now unlinks that IP from the host (the IP asset is kept, only `host_id` is cleared).
- Hosts list displays a project badge (with project color) based on linked IP assignments; multiple linked projects show a warning badge.
- Hosts page includes a collapsible search panel to filter by host name, vendor, notes, or linked IPs.
- Adding a host now uses the same right-side drawer interaction as editing, so create/edit actions stay visually consistent.
- Host deletion now uses the same right-side drawer pattern as host add/edit and IP delete flows, with destructive safeguards (acknowledgement checkbox + exact host-name confirmation) before enabling permanent delete. Deleting a host keeps all linked IP assets and automatically unassigns them from that host.

## Vendors

Vendors are managed in the shared Library page tabs and are selectable when creating or editing Hosts (API and UI).

- Vendor management uses the same right-side drawer pattern for create/edit/delete, including destructive confirmation by typing the exact vendor name.
- Vendors table now shows an **IPs** count column with how many active IP assets are currently linked through hosts for each vendor.

- UI route handlers are now organized as a modular package under `app/routes/ui/` (`auth.py`, `dashboard.py`, `ip_assets.py`, `hosts.py`, `ranges.py`, `settings.py`, `data_ops.py`, `connectors.py`) with shared helpers in `utils.py` and a single aggregated `router` exported from `app/routes/ui/__init__.py`.
- Developer compatibility note: `app/routes/ui/__init__.py` re-exports UI auth/session helpers (including `SESSION_COOKIE`) so existing integrations and tests continue working after modularization.

- API route handlers are now organized as a modular package under `app/routes/api/` (`auth.py`, `system.py`, `assets.py`, `hosts.py`, `metadata.py`, `imports.py`) with shared schemas/dependencies/helpers and a single aggregated `router` exported from `app/routes/api/__init__.py`.
- Developer compatibility note: `app/routes/api/__init__.py` re-exports auth dependency helpers (`get_current_user`, `require_editor`) for stable imports during the refactor.
