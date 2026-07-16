# ipocket overview

ipocket is a lightweight IP inventory app to track addresses and their project assignment.

## Highlights
- CRUD API for IP records (including permanent delete endpoint for editors only)
- Project management
- Project colors to quickly scan ownership in the IP assets list
- The IP Assets list at `/ui/ip-assets` is React/Vite/TypeScript-powered inside the existing Jinja application shell. It remains the primary inventory and project-assignment workflow and loads list rows, filter metadata, action policy, and pagination from `GET /api/ui/ip-assets`.
- IP assets list supports debounced live search and filtering (including an assignment dropdown) without full page reloads. Filter and pagination state stays synchronized with the browser URL, including Back/Forward navigation, and stale list responses are ignored.
- Project filter on IP assets now includes an `Unassigned` option to show only IPs without a project directly from the Project dropdown.
- Project assignment review is handled directly in the IP Assets list via the **Assignment** filter (`Unassigned only`); the dedicated Needs Assignment page has been removed.
- IP assets search results are sorted by numeric IP value (so `192.168.1.2` appears before `192.168.1.11`) instead of plain text ordering.
- IP assets list supports one-click filtering from table values: clicking a Project/Type chip applies that filter instantly, and Tag filtering uses an autocomplete builder with **OR**, **AND**, and **NOT** groups. Legacy `tag=...` URLs still map to **OR** matching.
- Selected tags in the top Tags filter keep each tag's configured catalog color, including chips added live from the autocomplete input.
- Selecting a Tags filter autocomplete suggestion with the mouse immediately adds its removable colored chip; Enter remains supported for keyboard selection. Selected chips are also restored visibly when loading or navigating back to a URL containing `tag_any`, `tag_all`, or `tag_not`.
- IP assets list includes an archived-only filter for reviewing soft-deleted records when needed.
- IP assets list includes pagination with a user-selectable page size (default 20) to keep large inventories manageable.
- Rows-per-page selector in the IP assets table footer is isolated from global table click handlers, so its dropdown stays open reliably while choosing a page size.
- Changing rows-per-page now preserves active IP assets filters (search text, project/type, assignment, archived state, and OR/AND/NOT tag filters) instead of resetting the list query.
- IP assets list keeps row actions and bulk-selection controls active after React pagination/filter updates (no manual page refresh needed).
- IP assets pagination/filtering/sorting now execute directly in SQL (including `LIMIT/OFFSET`) using persisted IPv4 integer values (`ip_int`) for fast numeric ordering, with text fallback ordering for non-IPv4 values.
- IP assets list rows use compact spacing for IP text and Project/Type chips to keep more records visible per page.
- IP assets table keeps `IP address`, `Project`, and `Type` columns narrow because their values are bounded, leaving more horizontal space for Tags and Notes.
- IP assets list uses a right-side drawer for both adding and editing IPs without leaving the list view.
- Saving an IP edit from the drawer returns to the list view instead of navigating to the detail page.
- Clearing Project in the IP edit drawer now correctly unassigns the IP (`project_id` becomes null) instead of keeping the previous project.
- Creating an IP from the drawer now also returns to the list view (preserving active filters/query state) instead of navigating to a detail URL.
- Editing or creating an IP from the drawer now preserves the currently visible pagination state (`page`/`per-page`) when returning to the list, including after HTMX page switches.
- After saving in the drawer, the list view restores the prior scroll position.
- Host assignment in the drawer only appears when the IP type is OS or BMC.
- Host assignment controls in IP Asset edit/create flows include a local host search box so large host inventories can be filtered before selecting a host.
- BMC IPs without a host assignment show a drawer action to create and assign a host named `server_<ip>`.
- IP assets list hides Host Pair to keep the table focused on assignment and editing fields.
- Data-table rows use one shared compact action pattern across IP Assets, Hosts, Ranges, Library catalogs, and User Management. The Actions column keeps a fixed reserved width but is visually empty until the row is hovered or receives keyboard focus; **Edit** and the `⋯` trigger then appear as matching lightweight ghost controls with a subtle 170 ms fade/slide transition. Individual controls receive a stronger background only on hover/focus. Touch/coarse-pointer and small-screen layouts keep the controls visible because hover is unavailable. **Delete** remains the final destructive item in the overflow menu. The menu is portal-positioned to avoid table clipping, follows RTL/LTR direction, supports keyboard navigation and Escape/outside-click close, and leaves room for future non-destructive actions.
- Delete is never exposed as a primary table-row button. Selecting it from the overflow menu still opens the existing confirmation drawer with the same acknowledgement and exact-value safeguards.
- Deleting an IP from the list now uses the same right-side drawer shell as Add/Edit but with strict modes: delete mode hides all edit inputs, shows a compact destructive confirmation summary (IP/Project/Type/Host), keeps the acknowledgement checkbox inline with its label, and for high-risk assets requires typing the exact IP before “Delete permanently” is enabled.
- The `/ui/ip-assets/{id}` React IP Asset Detail migration is complete. The page runs inside the existing authenticated Jinja shell and loads display data, OS/BMC host pairs, audit history, editor metadata, and action policy from `GET /api/ui/ip-assets/{id}/detail`; Viewer remains read-only, while the existing IP Asset `Editor` dependency gates edit, delete, and auto-host mutations.
- IP asset detail uses the shared card/chip visual language, including high-contrast project/tag colors, direct links for IP address, Host, and paired OS/BMC addresses, badge-styled audit actions with optional raw detail expansion, and accessible Edit/Delete drawers. Successful edits and auto-host actions refresh Detail and Audit Log without a full-page reload; permanent delete returns to `/ui/ip-assets`.
- The IP Asset Detail React mount preserves the shell's standard `24px` spacing between the page header, Details card, and Audit Log card.
- IP assets list includes bulk edit controls to update type, project assignment, add/remove tags, or overwrite notes across multiple IPs at once.
- IP assets list keeps tag cells compact: up to 3 chips are shown in-row, and extra tags move into a `+N more` popover (open on hover or click, with keyboard/outside-click close and inline tag search).
- The IP Assets React table opens `+N more` after a short hover delay and keeps the popover open while the pointer moves from the trigger into it; click and keyboard focus remain supported.
- IP assets list keeps Notes cells single-line to preserve row height; full note text appears in a hover/focus tooltip after a short pointer delay.
- IP assets table uses a fixed responsive layout so long Notes/Tags content does not force horizontal page scrolling.
- Tags on IP assets are now selected from existing Tag records (no free-text tag creation during assignment), with a dedicated Tags page to manage names and colors.
- Tag selection UI now uses a chip-based picker (`Add tags...`) with searchable dropdown suggestions, Enter/click add, chip remove (`×`), and Backspace removal of the last selected chip.
- Focusing or clicking `Add tags...` in IP Asset add/edit, bulk update, or detail drawers opens all currently unselected catalog tags; typing narrows the visible suggestions.
- Bulk edit tag picker no longer shows an empty suggestions panel by default; the suggestions dropdown now stays hidden until you focus/type in `Add tags...`.
- Bulk updates now open in a right-side drawer (matching Add/Edit/Delete flows) after selecting rows, keeping the table header compact while applying Type/Project/Tag changes to all selected IP assets.
- Bulk update drawer now shows **Common tags** across selected rows and lets operators mark shared tags for removal (sent as `remove_tags`) while still supporting additive tags in the same action.
- Bulk/update/delete redirects now clear stale toast query parameters (`bulk-error`, `bulk-success`, `delete-error`, `delete-success`) so old notifications are not re-shown after a later successful action.
- Tag chips now auto-pick a high-contrast text color (dark/light) based on each tag background color across the IP edit/add drawers, IP assets table tags, and tag popovers.
- Tags page now uses the same right-side drawer pattern as Projects/Vendors for create/edit/delete, including destructive confirmation by typing the exact tag name. The tags table also shows an **IPs** count column with how many active IP assets currently use each tag.
- Tag create drawer suggests a random tag color by default (instead of one fixed color), and users can override it before saving.
- Management overview dashboard with quick totals for IPs, hosts, vendors, and projects, with cards linking to the relevant detail lists. It is part of the incremental React/TypeScript migration; the existing Jinja application shell and sidebar remain in place, and React mounts preserve the shell's standard 24px spacing between page sections.
- CIDR-based subnet utilization report on the React-powered Management overview page that loads through `GET /api/management/overview` and shows loading, retryable error, empty, and populated states.
- Sidebar remains fixed-height with its own scroll to keep navigation and account actions accessible on long pages.
- UI pages advertise a local `/static/favicon.png` icon so browser tabs/bookmarks show the ipocket brand without external asset loading.
- The old fixed top header has been removed from the main layout to give pages more vertical space; branding remains in the left sidebar.
- UI templates keep behavior and styling in static assets. `app/static/app.css` is a small, ordered entrypoint that imports focused stylesheets from `app/static/css/` for foundations, shared components, forms, tables, workflows, and page-specific UI. Library, IP Assets List, and IP Asset Detail are React/Vite/TypeScript entries mounted inside the existing Jinja shell. The former IP Assets-specific HTMX/native-JavaScript entry has been removed; legacy direct create/edit/delete/bulk form routes remain available for compatibility.
- The sidebar account section shows Login when signed out and Logout when signed in.
- `/ui/login` is React/Vite/TypeScript-powered inside a lightweight Jinja shell with no application sidebar. The React form posts to `POST /api/ui/login`, but username normalization, generic authentication failures, inactive-user rejection, password verification, legacy SHA-256-to-bcrypt upgrades, persistent session creation, cookie signing, and return-target approval all remain server-side. Login return targets are normalized and restricted to local application paths; unsafe targets fall back to `/ui/ip-assets`. The legacy `POST /ui/login` form endpoint remains available and shares the same backend login helper.
- Password hashing now uses `passlib` with `bcrypt` (legacy SHA-256 hashes are upgraded to bcrypt after successful login).
- API bearer tokens and UI session cookies now resolve to persistent records in the SQLite `sessions` table, so authenticated sessions survive server restarts and multi-process scaling.
- UI session signing now requires `SESSION_SECRET` to be configured in non-testing environments; startup fails fast if it is missing or blank.
- Authenticated users can open the React-powered **Change Password** page from the sidebar account section (`/ui/account/password`) to rotate their own password by providing current password + new password confirmation. The Jinja route retains the standard application shell, while verification, hashing, self-only mutation, and USER audit logging remain server-side through `POST /api/ui/account/password`; the legacy `POST /ui/account/password` form route remains compatible through the same backend helper.
- In the sidebar account section, authenticated actions are grouped as a compact stack (`Change Password` + `Logout`) so account actions stay visually connected.
- User access model distinguishes `Editor` (data write) from `Superuser` (user management, plus Library catalog maintenance); read routes stay public except audit log, which still requires authentication.
- User management is available on the React-powered `/ui/users` page and writes changed user-management actions to audit logs with target type `USER`.
- `/ui/users` keeps the authenticated Jinja application shell but loads its table and drawers from the local Vite entry at `/static/react/users/users.js`.
- The page and all `GET/POST/PATCH/DELETE /api/ui/users` endpoints are restricted to authenticated Superusers; Viewer and Editor requests are forbidden by the backend.
- User create/edit/delete uses the same right-side drawer pattern as other management pages, while password hashing, Viewer/Editor role semantics, Superuser protection, last-active-Superuser safeguards, self-delete prevention, and exact-username deletion confirmation remain server-enforced.
- Legacy `/ui/users` HTML form mutation routes remain compatible and share validation, mutation, and audit helpers with the JSON API.
- The sidebar footer shows build metadata (`version/commit/build time`) whenever the sidebar is visible, including signed-out views.
- IP ranges page supports editing and deleting saved CIDR ranges for cleanup, with a confirmation step that requires typing the exact range name.
- Saved ranges use the shared hover/focus-revealed Edit + overflow-menu row action pattern so table actions stay visually consistent across pages.
- Range addresses view includes Status, Host Pair, and Notes for used IPs in subnet drill-downs.
- Range addresses view is React/Vite/TypeScript-powered inside the standard Jinja shell. It loads range metadata, filter catalogs, action policy, rows, normalized query state, and pagination from `GET /api/ui/ranges/{range_id}/addresses`.
- Range addresses view supports debounced IP search plus separate `Project`/`Type` dropdown filters, chip-based tag filtering, status filtering (`all/used/free`), and pagination (`per-page` + previous/next). State stays in the browser URL, Back/Forward restores it, stale requests are ignored, and legacy `#used`/`#free` links map to status filters.
- Range addresses table keeps tag cells compact like IP assets: up to 3 tags render inline, and additional tags collapse behind a `+N more` popover with hover/click open, keyboard close, and inline tag search. Clicking any tag chip in-row or inside the popover instantly adds it to the range Tags filter.
- Range addresses view uses accessible React drawers for “Add” (free IPs) and “Edit” (used IPs). The JSON mutations reuse existing IP asset validation, repository writes, and audit behavior; legacy HTML form routes remain available.
- Range address page sections use the standard 24px vertical spacing between the header, details, filters, and address table cards.
- IP ranges page now opens “Add IP Range” inside a right-side drawer instead of an inline card, keeping create UX consistent with Hosts/IP assets flows.
- IP ranges page now opens range editing in a right-side drawer too, so Edit keeps users on `/ui/ranges` like Hosts and IP assets.
- IP ranges page now performs delete confirmation inside a matching right-side drawer (with explicit acknowledgement + exact-name typing) so destructive actions follow the same interaction pattern as IP asset delete.
- Range delete drawer now reliably displays CIDR/usage context from the selected row (including when opened inline), reducing confirmation mistakes.
- IP ranges render in a single unified table card (name/CIDR/usable/used/free/utilization/actions), with Used/Free counts staying clickable for address drill-down and row-level actions kept compact.
- The `/ui/ranges` list is React/Vite/TypeScript-powered while retaining the existing Jinja shell/sidebar, table styling, drawer interactions, validation messages, query-based edit/delete links, and address drill-down URLs. It reads and mutates range data through `/api/ui/ranges`; legacy HTML form routes remain available for compatibility.
- Jinja-driven pages continue to share drawer open/close behavior through `app/static/js/drawer.js`; the React Ranges page mirrors the same classes, spacing, close confirmation, and footer states in a typed component.
- Reusable drawer shell markup is centralized in `app/templates/macros/drawer.html` for Jinja-driven drawer pages, while the React Ranges implementation keeps an equivalent `RangeDrawer` component.
- `/ui/projects` is React/Vite/TypeScript-powered while the Jinja application shell, sidebar, session cookie, and role rules remain unchanged. The page uses focused `/api/ui/library/projects`, `/api/ui/library/vendors`, and `/api/ui/library/tags` endpoints; legacy HTML form and redirect routes remain available for compatibility.
- `/ui/hosts` and `/ui/hosts/{id}` are React/Vite/TypeScript-powered inside the existing Jinja shell. The list uses public `GET /api/ui/hosts`, while Host Detail uses public `GET /api/ui/hosts/{id}/detail` and preserves the existing OS/BMC/Other grouping, project/tag colors, empty states, and links to IP Asset detail pages. Host list POST/PATCH/DELETE still require Editor or Superuser. The list preserves filter/pagination state in the URL with browser back/forward support, debounces text search, rejects stale responses, and refreshes the table after drawer mutations without a full-page reload. Legacy `?edit=<id>` and `?delete=<id>` links use server bootstrap so their Drawer target is resolved independently of the current filters or pagination, with missing Hosts returning 404.
- Projects, Vendors, and Tags keep the existing right-side drawer UX for create/edit/delete, dirty-close confirmation, Escape/overlay close, exact-name destructive confirmation, validation messages, usage counts, and tab/query links. Successful mutations refresh only the active table rather than reloading the full page.
- Library API validation preserves project/tag color normalization, tag-name normalization, and random Tag create colors. Viewer remains read-only, while Editor and Superuser can create, edit, and delete Library catalog entries. Authentication redirects detected by React return the browser to the login flow.
- The Library page uses one shared "Catalog Settings" header with compact segmented tabs (Projects/Tags/Vendors) and a tab-aware primary action button (New Project/Tag/Vendor) to keep controls in one place.
- The Library header primary action button now reliably opens the matching create drawer on all tabs (Projects/Tags/Vendors).
- The Projects and Tags tab tables now use compact row spacing so catalog rows stay denser and easier to scan.
- Projects table now shows an **IPs** count column so you can quickly see how many active IP assets are currently assigned to each project.
- Use the shared **Data Ops** page (Import/Export tabs) for round-trip workflows.
- Export data as CSV, JSON, or bundle (JSON/ZIP) from the Data Ops Export tab.
- `ip-assets.csv` export ordering is numeric by IP value (`10.0.0.2` before `10.0.0.10`), including fallback numeric parsing when legacy rows have null `ip_int`.
- `hosts.csv` export now includes `project_name`, `os_ip`, and `bmc_ip` so host exports can round-trip through CSV import without manual column edits.
- Import data from bundle.json or CSV with dry-run support and upserts from the Data Ops Import tab.
- Upload Nmap XML from the Data Ops Import tab to discover reachable IPs and add them as `OTHER` assets, with inline example commands.
- Data Ops and API import uploads enforce a per-file size cap of `10 MB` and return HTTP `413` when exceeded.
- Sidebar includes a **Connectors** page with tabs (`Overview` / `vCenter` / `Prometheus` / `Elasticsearch` / `Cassandra` / `Ceph` / `Kubernetes`) so operators can run import connectors directly from UI.
- **Connectors → vCenter** supports both `dry-run` and `apply` execution modes, now runs as a background job from UI to avoid long request blocking, and shows an in-page execution log/status on the connector tab.
- Manual vCenter connector is available via `python -m app.connectors.vcenter` (ESXi hosts as `OS` + tag `esxi`, VMs as `VM`) with file export mode and local DB dry-run/apply modes (`--db-path`); on update it always overwrites `type`, merges connector tags into existing tags, and only writes connector notes when the existing note is empty.
- **Connectors → Prometheus** imports IPs from Prometheus `api/v1/query` vector results by extracting IPv4 values from a chosen label (for node_exporter this is commonly `instance`), supports `dry-run`/`apply` from UI background jobs, keeps a CLI path via `python -m app.connectors.prometheus`, preserves non-empty existing IP notes and existing `type` during updates, and shows per-IP dry-run change details (`CREATE`/`UPDATE`/`SKIP` with field-level diffs).
- **Connectors → Elasticsearch** imports node IPs from Elasticsearch `/_nodes/http,transport`, supports `dry-run`/`apply` from UI background jobs and CLI via `python -m app.connectors.elasticsearch`, supports optional authentication (API key or username/password), can optionally add the normalized Elasticsearch `cluster_name` as a tag on every imported node IP, auto-refreshes the tab while a run is queued/running, always merges connector tags into existing tags, overwrites `type`/`project` when provided, and overwrites notes only when a connector note is provided.
- **Connectors → Cassandra** imports node IPs from Cassandra driver cluster metadata, supports `dry-run`/`apply` from UI background jobs and CLI via `python -m app.connectors.cassandra`, supports optional username/password authentication plus TLS/insecure TLS toggles, can optionally add the normalized Cassandra `cluster_name` as a tag on every imported node IP, auto-refreshes the tab while a run is queued/running, always merges connector tags into existing tags, overwrites `type`/`project` when provided, and overwrites notes only when a connector note is provided.
- **Connectors → Ceph** imports host IPs from Ceph Dashboard `GET /api/host`, supports `dry-run`/`apply` from UI background jobs and CLI via `python -m app.connectors.ceph`, authenticates through `POST /api/auth`, creates/updates matching Hosts from Ceph `hostname`, links imported IP assets to those Hosts, can optionally add normalized cluster/label tags, auto-refreshes the tab while a run is queued/running, always merges connector tags into existing tags, overwrites `type`/`project`/`host` when provided, and overwrites notes only when a connector note is provided.
- **Connectors → Kubernetes** imports Node `InternalIP` addresses from Kubernetes `GET /api/v1/nodes`, supports `dry-run`/`apply` from UI background jobs and CLI via `python -m app.connectors.kubernetes`, authenticates with a bearer token, creates/updates matching Hosts from Node `metadata.name`, links imported IP assets to those Hosts, can optionally add normalized cluster/label tags, auto-refreshes the tab while a run is queued/running, always merges connector tags into existing tags, overwrites `type`/`project`/`host` when provided, and overwrites notes only when a connector note is provided.
- Connector dry-run/apply imports execute in-process with the active DB connection (no loopback HTTP request to ipocket `/import/bundle`).
- Successful `apply` executions for bundle/CSV imports and connector runs now write run-level audit entries (`target_type=IMPORT_RUN`) with source + create/update/skip/warning/error summary; `dry-run` executions are not audited at run level.
- Prometheus metrics on `/metrics`
- Prometheus SD endpoint on `/sd/node` with project grouping
- Kubernetes deployment via Helm chart (`helm/ipocket`) with configurable image, persistence, ingress, and bootstrap/session secrets
- Audit logging for IP asset create/update/delete actions is surfaced on the IP detail page and the authenticated, read-only `/ui/audit-log` history page. The global Audit Log is React/Vite/TypeScript-powered inside the standard Jinja application shell, keeps server-side repository pagination and ordering, and is readable by Viewer, Editor, and Superuser roles.
- Database schema managed through Alembic migrations
- SQLite connections are configured for concurrent request handling (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`).
- Repository data-access layer is modularized under `app/repository/` (assets, hosts, ranges, metadata, users, audit, summary), while `app.repository` remains the stable import surface via package re-exports.
- Repository operations now run through SQLAlchemy ORM/Core sessions (`app/schema.py`) across assets/hosts/ranges/metadata/users/audit/summary/sessions, while keeping backward compatibility for callers that still pass `sqlite3.Connection` objects.
- Internal IP-asset repository logic is further split into focused helpers: `app/repository/_asset_filters.py` (filter query assembly), `app/repository/_asset_tags.py` (tag mappings/persistence), and `app/repository/_asset_audit.py` (audit change summaries); `app/repository/assets.py` remains the backward-compatible public API module.
- The IP asset listing path adds DB indexes (`ip_assets` archived/filter columns plus tag lookup indexes) to keep paginated list and tag-filter queries responsive on larger datasets.
- IP assets now persist an optional integer IPv4 representation (`ip_int`) for DB-side numeric sorting and CIDR range utilization queries at larger scale.
- Creating an IP that matches an existing archived record now restores (un-archives) that same record instead of returning a duplicate-address conflict.

## Note
Owner support has been removed in development phase, so assignment is now project-only.


## Hosts

Hosts can be linked to a vendor from the shared **Vendors** catalog.

- Hosts list uses a right-side edit drawer for name, vendor, notes, single-value OS/BMC IP updates, and project/status context (with inline IPv4 validation); changing project updates linked IP assignments.
- Host add form supports selecting a project plus inline OS/BMC IP inputs; when a project is selected, newly linked IP assets inherit that project during host creation.
- Hosts list reveals Edit and the overflow trigger only when a row is hovered or focused, and places Delete in the overflow menu.
- Hosts list shows linked OS and BMC IP addresses alongside the total linked IP count; OS/BMC addresses link directly to their IP asset detail pages.
- Hosts list uses a compact fixed-layout table sized to the page width so normal desktop views do not need horizontal scrolling.
- Hosts list reserves the same narrow action width as other data tables, preventing layout shifts when controls appear.
- Hosts list shows an **IP tags** column with deduplicated tags from linked active IP assets; these are IPAsset tags and do not create host-level tag storage. To keep the table compact and aligned with IP Assets, host tag chips use the same compact sizing, rows show up to 2 tag chips, and additional tags collapse behind a searchable `+N more` popover anchored beside the triggering row. The popover opens on hover, focus, or click and closes with Escape or outside click. Clicking any inline or popover tag immediately applies that tag to the Hosts filter.
- IP Asset detail pages show the paired host address only for OS/BMC assets: OS records show linked BMC addresses, and BMC records show linked OS addresses. Detail values for the IP address, Host, and paired OS/BMC addresses link directly to their detail pages.
- In Host edit, clearing an OS/BMC IP from the drawer and saving now unlinks that IP from the host (the IP asset is kept, only `host_id` is cleared).
- Hosts list displays a project badge (with project color) based on linked IP assignments; multiple linked projects show a warning badge.
- Hosts page includes a collapsible React search panel with text search plus Vendor, Project, Assignment, linked/free Status, and tag filters. Filters are reflected in the query string, text search is debounced, browser back/forward restores filter state, and tag filters match tags on linked active IP assets.
- Hosts pagination is integrated into the table card: the footer shows the visible row range and total, keeps the rows-per-page selector and previous/next controls in one compact aligned group, and stacks cleanly on narrow screens.
- Host create/edit/delete uses an accessible right-side React drawer with Escape/overlay close, unsaved-change confirmation, inline validation errors, and acknowledgement plus exact-name confirmation for delete. Deleting a Host keeps linked IP assets and clears their Host assignment.
- Host drawer initial focus now runs only when the drawer opens or changes mode, so typing in Notes or another controlled field no longer moves the cursor back to Name after the first character.
- Adding a host now uses the same right-side drawer interaction as editing, so create/edit actions stay visually consistent.
- Host detail pages use the shared detail layout: header metadata chips, a Details card, and grouped OS/BMC/other linked-IP tables with project, tag, and notes context plus empty states.
- Host deletion now uses the same right-side drawer pattern as host add/edit and IP delete flows, with destructive safeguards (acknowledgement checkbox + exact host-name confirmation) before enabling permanent delete. Deleting a host keeps all linked IP assets and automatically unassigns them from that host.

## Vendors

Vendors are managed in the shared Library page tabs and are selectable when creating or editing Hosts (API and UI).

- Vendor management uses the same right-side drawer pattern for create/edit/delete, including destructive confirmation by typing the exact vendor name.
- Vendors table now shows an **IPs** count column with how many active IP assets are currently linked through hosts for each vendor.

- UI route handlers are organized under `app/routes/ui/` with domain packages for larger areas:
  `app/routes/ui/ip_assets/`, `app/routes/ui/hosts/`, `app/routes/ui/ranges/`, `app/routes/ui/settings/`, plus focused modules such as `auth.py`, `account.py`, `dashboard.py`, and `data_ops.py`. `app/routes/ui/__init__.py` remains the single aggregated router entrypoint.
- Connector UI routes are split under `app/routes/ui/connector_routes/`: each connector owns its validation, execution, background job wrapper, and POST route; shared form state, page rendering, job storage, and Prometheus preview formatting live in focused support modules. `app/routes/ui/connectors.py` is only the stable router-composition facade.
- UI utility internals are split into `app/routes/ui/_utils/` modules (`session.py`, `rendering.py`, `parsing.py`, `assets.py`, `exporting.py`) and `app/routes/ui/utils.py` now acts as a compatibility facade so existing imports stay stable.
- UI flash notifications are cookie-backed and now truncate each message to a safe length (`400` chars) before cookie encoding to avoid oversized cookie failures.
- IP-assets helper logic lives in `app/routes/ui/ip_assets/helpers.py`, while routes are split by concern (`listing.py`, `forms.py`, `actions.py`) to keep assignment/listing and mutation flows separate without changing endpoint behavior.
- Developer compatibility note: `app/routes/ui/__init__.py` re-exports UI auth/session helpers (including `SESSION_COOKIE`) so existing integrations and tests continue working after modularization.

- API route handlers are now organized as a modular package under `app/routes/api/` (`auth.py`, `system.py`, `assets.py`, `hosts.py`, `metadata.py`, `imports.py`) with shared schemas/dependencies/helpers and a single aggregated `router` exported from `app/routes/api/__init__.py`.
- Developer compatibility note: `app/routes/api/__init__.py` re-exports auth dependency helpers (`get_current_user`, `require_editor`) for stable imports during the refactor.
