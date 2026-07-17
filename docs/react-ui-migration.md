# React UI migration inventory

The primary UI migration is complete. FastAPI and Jinja remain the shared
application shell, navigation, session/flash boundary, and compatibility-form
renderer. React owns the normal interactive content for 15 primary pages and
loads focused JSON from `/api/ui/...` endpoints (plus the existing
`/api/management/overview`). This does **not** mean that Jinja, HTMX, Alpine, or
server-rendered forms have been removed.

## Primary React pages

“React primary page” means the normal navigation target. “React page with
lightweight Jinja mount” identifies secondary/detail/account pages whose Jinja
template is only a shell and mount point.

| Page / primary route | React entry | Bootstrap or data endpoint | Jinja template | Status | Retained compatibility |
|---|---|---|---|---|---|
| Login `/ui/login` | `login` | `POST /api/ui/login` | `login.html` | React primary page | `POST /ui/login`, safe local `return_to`, and server-rendered login errors remain. |
| Management `/ui/management` | `management` | `GET /api/management/overview` | `management.html` | React primary page | Public read policy is unchanged. |
| IP Assets `/ui/ip-assets` | `ip-assets` | `GET /api/ui/ip-assets` | `ip_assets_list.html` | React primary page | Public read/Viewer policy, legacy bulk POST, toast query parameters, and direct forms remain. |
| IP Asset detail `/ui/ip-assets/{id}` | `ip-asset-detail` | `GET /api/ui/ip-assets/{id}/detail` | `ip_asset_detail.html` | React page with lightweight Jinja mount | Authenticated Viewer read; Editor mutations and direct forms remain. |
| Hosts `/ui/hosts` | `hosts` | `GET /api/ui/hosts` | `hosts.html` | React primary page | `HX-Request` still returns `partials/hosts_table.html`; legacy form POST errors bootstrap the React drawer. |
| Host detail `/ui/hosts/{id}` | `host-detail` | `GET /api/ui/hosts/{id}/detail` | `host_detail.html` | React page with lightweight Jinja mount | The data endpoint remains authenticated; an expired session returns to login. |
| Ranges `/ui/ranges` | `ranges` | `GET /api/ui/ranges` | `ranges.html` | React primary page | Legacy create/edit/delete POST validation is serialized into the React bootstrap. |
| Range addresses `/ui/ranges/{id}/addresses` | `range-addresses` | `GET /api/ui/ranges/{id}/addresses` | `range_addresses.html` | React primary page | Legacy add/edit POST routes and `#used`/`#free` links remain. |
| Library `/ui/projects` | `library` | `GET /api/ui/library/{projects,vendors,tags}` | `projects.html` | React primary page | Project/Tag/Vendor HTML POST error pages and direct redirect routes remain. |
| Users `/ui/users` | `users` | `GET /api/ui/users` | `users.html` | React primary page | Superuser-only policy and legacy form POST errors remain. |
| Audit Log `/ui/audit-log` | `audit-log` | `GET /api/ui/audit-log` | `audit_log_list.html` | React primary page | Authenticated read-only policy remains. |
| Account Password `/ui/account/password` | `account-password` | `POST /api/ui/account/password` | `account_password.html` | React page with lightweight Jinja mount | `POST /ui/account/password` still renders validation errors through the same helper. |
| Data Operations `/ui/import` | `data-ops` | `GET /api/ui/data-ops`; `POST /api/ui/import/{bundle,csv,nmap}` | `data_ops.html` | React primary page | Multipart HTML POST results still render `import.html`; `/ui/export` selects the Export tab. |
| Connectors `/ui/connectors` | `connectors` | `GET /api/ui/connectors`; run/job endpoints below it | `connectors.html` | React primary page | Six connector HTML POST routes still render `connectors_legacy.html` on validation/results. |
| About `/ui/about` | `about` | `GET /api/ui/about` | `about.html` | React page with lightweight Jinja mount | Authenticated policy and direct `/health`/`/metrics` links remain. |

All entries above are registered in `frontend/vite.config.ts`. A production
build emits one entry at `app/static/react/<entry>/<entry>.js`, plus hashed
shared chunks under `app/static/react/shared/`. The test-side manifest in
`tests/react_ui_manifest.py` drives page mounts, endpoint smoke coverage, Vite
entry checks, and bundle-reference checks from one list.

## Generated-artifact policy

The completed migration treats the entire `app/static/react/` tree as generated
build output. It is ignored by Git and must not be committed. Local development,
frontend CI, and the Docker frontend stage regenerate all entry bundles and
hashed shared chunks from the tracked `frontend/` sources and lockfile. The
runtime Docker stage copies the complete generated directory from the Node 22
build stage.

## Retained GET compatibility and redirect routes

| Route | Classification | Behavior / reason retained |
|---|---|---|
| `/` | Redirect-only route | Sends the browser to `/ui/ip-assets`. |
| `/ui/ip-assets/new` | Intentional legacy compatibility page | Direct create form and no-JavaScript/server validation path using `ip_asset_form.html`. |
| `/ui/ip-assets/{id}/edit` | Intentional legacy compatibility page | Direct edit form using `ip_asset_form.html`. |
| `/ui/ip-assets/{id}/delete` | Intentional legacy compatibility page | Direct exact-value delete confirmation using `ip_asset_delete_confirm.html`. |
| `/ui/hosts/{id}/delete` | Redirect-only route | Opens the React Hosts delete drawer through `?delete={id}`. |
| `/ui/ranges/{id}/edit` | Redirect-only route | Opens the React Ranges edit drawer through `?edit={id}`. |
| `/ui/ranges/{id}/delete` | Redirect-only route | Opens the React Ranges delete drawer through `?delete={id}`. |
| `/ui/projects/{id}/edit`, `/delete` | Redirect-only routes | Open the corresponding React Library drawer. |
| `/ui/tags/{id}/edit`, `/delete` | Redirect-only routes | Redirect into `/ui/projects?tab=tags`. |
| `/ui/vendors/{id}/edit`, `/delete` | Redirect-only routes | Redirect into `/ui/projects?tab=vendors`. |
| `/ui/tags`, `/ui/vendors` | Intentional legacy compatibility pages | Retain server-rendered Library form/error flows through `projects.html` and its partials. |
| `/ui/export` | React page with lightweight Jinja mount | Compatibility entry for Data Operations with the Export tab selected. |
| `/ui/import-nmap` | Redirect-only route | Preserves the old bookmark and sends it to `/ui/import`. |

The authenticated download GETs under `/export/` (`ip-assets.csv/json`,
`hosts.csv/json`, `vendors.csv/json`, `projects.csv/json`, and
`bundle.json/zip`) are intentional Data Operations downloads, not page
templates. They remain unchanged.

## Frontend foundation consolidation

The framework-independent `frontend/src/shared/apiClient.ts` is the common
transport for About, Management Overview, the global Audit Log, Host Detail,
and Ranges while endpoint-specific types and page-domain adapters stay in each
page's `api.ts` module. The client keeps requests same-origin with the existing
session cookie, supports JSON and FormData request bodies, forwards abort
signals, handles empty responses, and exposes typed HTTP errors for FastAPI
validation/detail payloads and non-JSON failures. Validation errors also expose
normalized message arrays for form-oriented callers without changing the
existing primary error message, status, or payload. The client detects API
redirects to `/ui/login`; each migrated page retains its established
`return_to` policy and user-facing error behavior.

Phase 2 moves Host Detail's read-only request and the complete Ranges
fetch/create/update/delete flow onto that transport. Ranges is the first full
CRUD page to use the shared client. Its endpoint URLs, methods, JSON payloads,
204 delete handling, drawer behavior, FastAPI validation messages, non-JSON
fallback, and `/ui/login?return_to=/ui/ranges` redirect are unchanged. Host
Detail continues to preserve cancellation, its stable network/404/HTTP
messages, and its existing page-owned authentication callback.

JSON remains the default response mode. Callers that need binary data can ask
for a native `Blob` or raw `Response`, so the shared transport does not force
downloads through JSON parsing. This capability is tested but the existing
download links have not been migrated in this phase.

Range Addresses, Hosts listing, Account Password, Login, Users, Library, IP
Assets, Data Operations, and Connectors remain deferred from shared-client
consolidation. Multipart uploads, native downloads, and other mutation-heavy
page API modules are candidates for later, separately tested phases; their
current behavior and authentication policy are unchanged.

No registered GET route is classified as obsolete/unreachable. The unreachable
artifacts were templates and partials left behind after their routes had moved.

## Conservative cleanup evidence

Repository-wide route render calls, Jinja `include`/`import` references, static
references, and tests were checked before deletion. The following files had no
active route renderer, no retained-template include, and no compatibility or
no-JavaScript consumer:

- `templates/export.html`, `owners.html`, `tags.html`, and `vendors.html`;
- `templates/range_edit.html`, `range_delete_confirm.html`, and
  `host_delete_confirm.html` (their GET routes now redirect to React drawers);
- `templates/partials/ip_assets_table.html` and `ip_table_rows.html` (the IP
  Assets list no longer has an HTMX response branch);
- `templates/partials/export_tab_content.html` and `import_tab_content.html`
  (React owns Data Operations; `import.html` remains the full legacy POST result).

The cleanup deliberately retains `connectors_legacy.html`, `import.html`,
`ip_asset_form.html`, `ip_asset_delete_confirm.html`, `projects.html`,
`hosts.html`, `ranges.html`, the three Library tab partials, and
`partials/hosts_table.html` because active compatibility POST, validation,
bootstrap, or HTMX routes render them.

## Browser dependencies

`base.html` continues to load the small shared dependency set globally. A more
complex route asset loader was not introduced for this closeout.

| Dependency | Active consumer |
|---|---|
| HTMX | Hosts list compatibility requests and `partials/hosts_table.html`; `app/static/js/hosts.js` remains available for that legacy flow. |
| Alpine | Server-rendered Project/Tag/Vendor compatibility drawers after legacy HTML form submissions. |
| `toast.js` | Shell flash/toast messages, including compatibility redirects. |
| `tag-picker.js` | Direct IP Asset create/edit forms and retained Jinja form flows. |
| `host-select-search.js` | Direct IP Asset create/edit Host selection. |
| `drawer.js`, `projects.js`, `tags.js`, `vendors.js` | Retained server-rendered Library drawers. |

## Authentication and authorization audit

The closeout does not change server policy:

- public inventory reads remain public for Management, IP Assets list, Hosts
  list, Ranges, and Range Addresses; their payloads expose `can_edit=false` to
  signed-out/View-only clients;
- About, Audit Log, Data Operations, Connectors, Library API data, Host Detail,
  and IP Asset Detail require an authenticated session;
- Users page/data/mutations require Superuser;
- inventory, range, library, import-apply, and connector-apply mutations repeat
  Editor authorization on the server; Viewer controls are hidden/disabled but
  are never the enforcement boundary;
- password changes are self-only and connector bootstrap/job responses omit
  submitted secrets.

Host Detail and Connectors now detect an API login redirect and hand navigation
back to `/ui/login?return_to=...`, matching the other React pages. This is a
client auth-expiry correction only; endpoint access policy did not change.

## Adding another React page

1. Add `frontend/src/<entry>/main.tsx` and focused component/API tests.
2. Register the entry in `frontend/vite.config.ts`.
3. Add a lightweight Jinja mount with a unique root ID, endpoint data
   attribute, and `/static/react/<entry>/<entry>.js` script.
4. Add the page once to `tests/react_ui_manifest.py`; the consolidated smoke
   and bundle tests will then cover it.
5. Keep authorization in the API dependency, handle login redirects in the
   client when the page shell can render signed out, and document any retained
   compatibility route here.
6. Run the backend/frontend verification commands in `docs/how-to-run.md` and
   commit the source and configuration changes only; do not edit or commit the
   generated Vite output.
