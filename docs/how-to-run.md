# How to run

## Requirements
- Python 3.11+
- Node.js 22+ and npm (only for building/testing React UI assets locally)
- SQLite (built-in)
- HTTP client support comes from the pip-installed `httpx` package in `requirements.txt`; ipocket does not ship a local `httpx/` package in the repo to avoid import shadowing.
- Cassandra connector support comes from the pip-installed `cassandra-driver` package in `requirements.txt`.

## Run locally
Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and build the React UI:

```bash
cd frontend
npm ci
npm run build
cd ..
```

The build writes the Management, Ranges, Library, Hosts list, Host Detail, IP
Asset Detail, and User Management entry bundles to
`app/static/react/management/management.js` and
`app/static/react/ranges/ranges.js`, and
`app/static/react/library/library.js` and
`app/static/react/hosts/hosts.js` and
`app/static/react/host-detail/host-detail.js` and
`app/static/react/ip-asset-detail/ip-asset-detail.js` and
`app/static/react/users/users.js`, with shared chunks under
`app/static/react/shared/`. Re-run `npm run build` after changing React sources.
The Docker image builds all React entrypoints automatically in a separate Node
stage; Node.js is not included in the final runtime image.

Initialize the database (runs migrations):

```bash
alembic upgrade head
```

After pulling updates, rerun `alembic upgrade head` to apply the latest schema/index migrations (including `ip_int` for SQL-based IPv4 sorting and subnet utilization filtering).

The migration runner reads `IPAM_DB_PATH` (defaults to `ipocket.db`) to locate the
SQLite file.

At runtime, each new SQLite connection enables WAL mode and applies
`synchronous=NORMAL` with a `busy_timeout` of 5000ms to reduce
`database is locked` errors under concurrent requests.

Reset the database for local dev (removes data):

```bash
rm -f ipocket.db
alembic upgrade head
```

Create a new migration (auto-generate from SQLAlchemy models):

```bash
alembic revision --autogenerate -m "describe_change"
```

Run the web app:

```bash
uvicorn app.main:app --reload
```

## Run with Docker
Build the image:

```bash
docker build -t ipocket:latest .
```

Run the container (persisting SQLite in a local `data/` directory):

```bash
mkdir -p data
docker run --rm -p 8000:8000 -v "$(pwd)/data:/data" ipocket:latest
```

The container runs `alembic upgrade head` on startup and stores the SQLite
database at `/data/ipocket.db`.

## Run with Docker Compose
The provided `docker-compose.yml` mounts the SQLite database directory outside
the container and sets bootstrap superuser credentials.

```bash
mkdir -p data
docker compose up --build
```

The app will persist data in `./data/ipocket.db` and is available at
http://127.0.0.1:8000.

Defaults for the bootstrap superuser are:
- `ADMIN_BOOTSTRAP_USERNAME=admin`
- `ADMIN_BOOTSTRAP_PASSWORD=admin-pass`

## Run with Helm (Kubernetes)
The repository includes a Helm chart at `helm/ipocket`.

Create a values file (recommended) with at least a strong session secret and
bootstrap superuser credentials:

```yaml
sessionSecret: "replace-with-a-long-random-secret"
adminBootstrap:
  username: "admin"
  password: "change-me"
image:
  repository: ipocket
  tag: "latest"
```

Install into namespace `ipocket`:

```bash
kubectl create namespace ipocket --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install ipocket ./helm/ipocket -n ipocket -f values-ipocket.yaml
```

Port-forward and open the UI:

```bash
kubectl -n ipocket port-forward svc/ipocket-ipocket 8000:8000
```

The chart runs `alembic upgrade head` before starting the app, exposes the
service on port `8000`, and stores SQLite data at `/data/ipocket.db`
(persistent volume enabled by default).

## Offline environments
Docker deployments default to local/static assets (CSS + JS like htmx) so the UI
renders without downloading from public CDNs. Non-Docker runs will load the
Inter font from Google Fonts and htmx/Alpine.js from CDNs by default. Library
Projects, Vendors, and Tags are served from the locally built React bundle, so
their table and drawer workflows do not depend on Alpine or a remote JavaScript
host. The Tags create drawer requests its suggested random color from the
focused UI API.
The browser favicon is always served locally from `/static/favicon.png`.
The `/static/app.css` stylesheet is the stable CSS entrypoint; it loads the
ordered, focused modules under `/static/css/`. When adding styles, place shared
rules in the matching module and page-only rules in that page's module, while
keeping the import order in `app.css` unchanged unless the cascade is intentionally
being updated.
Management Overview, IP Ranges, Library, the Hosts list, Host Detail, IP Asset
Detail, User Management, and Change Password are incrementally migrated React
pages.
FastAPI/Jinja still renders the application shell and sidebar. Management loads
dashboard data from `GET /api/management/overview`; `/ui/ranges` uses
`GET/POST /api/ui/ranges` and `PATCH/DELETE /api/ui/ranges/{id}` for its table
and drawer workflows. The Ranges implementation preserves CIDR validation,
duplicate handling, exact-name delete confirmation, `?edit=<id>` and
`?delete=<id>` entry links, and Used/Free address drill-down links. Production
bundles are served locally from `/static/react/management/management.js` and
`/static/react/ranges/ranges.js`. Library uses
`GET/POST /api/ui/library/{projects|vendors|tags}` plus
`PATCH/DELETE /api/ui/library/{entity}/{id}`, and its bundle is served from
`/static/react/library/library.js`. Existing `tab`, `edit`, and `delete` query
parameters and legacy HTML mutation routes remain compatible.
The Hosts list uses `GET/POST /api/ui/hosts` and
`PATCH/DELETE /api/ui/hosts/{id}` from `/static/react/hosts/hosts.js`.
`GET /api/ui/hosts` is public like the other inventory read routes and returns
`can_edit=false` for signed-out requests. POST/PATCH/DELETE use the existing UI
session cookie and allow only Editor and Superuser; Viewer is read-only.
Legacy `/ui/hosts?edit=<id>` and `/ui/hosts?delete=<id>` links receive a
server-resolved Drawer bootstrap, so the target remains available when filters
or pagination hide it, and an unknown Host returns 404. `/ui/hosts/{id}` keeps
the Jinja shell/sidebar and mounts `/static/react/host-detail/host-detail.js`;
its display-ready data comes from public `GET /api/ui/hosts/{id}/detail`.
Legacy Host form/partial routes remain available.
`/ui/users` keeps the authenticated Jinja shell/sidebar and mounts
`/static/react/users/users.js`. Its table and drawer workflows use
`GET/POST /api/ui/users` and `PATCH/DELETE /api/ui/users/{id}`. The page and
every endpoint remain server-authorized for Superusers only; Viewer and Editor
requests are forbidden. Password hashing, role protection, last-active-
Superuser safeguards, exact-username deletion confirmation, and USER audit
entries remain backend responsibilities. Legacy HTML form mutation routes are
retained for compatibility.
`/ui/account/password` keeps the authenticated Jinja shell/sidebar and mounts
`/static/react/account-password/account-password.js`. Its form submits to
`POST /api/ui/account/password`; current-password verification, bcrypt hashing,
self-only mutation, and the single USER audit entry remain server-side. The
legacy `POST /ui/account/password` form route uses the same validation and
mutation helper and remains available for compatibility.
`/ui/ip-assets/{id}` keeps the authenticated Jinja shell/sidebar and mounts
`/static/react/ip-asset-detail/ip-asset-detail.js`. It reads
`GET /api/ui/ip-assets/{id}/detail` and uses focused PATCH, DELETE, and
`POST .../auto-host` endpoints. Viewer can read Detail and Audit Log; mutations
reuse the existing IP Asset Editor-only dependency. Legacy edit/delete/auto-host
HTML routes remain available.
The IP Assets list stays fully local and unchanged: `/static/js/ip-assets.js` is a native
ES-module entrypoint whose focused dependencies are served from
`/static/js/ip-assets/`. No bundler, package install, or external JavaScript host
is required for these modules.
To force local assets in any environment, set:

```
IPOCKET_DOCKER_ASSETS=1
```

To explicitly allow remote font loading (even in Docker), set:

```
IPOCKET_DOCKER_ASSETS=0
```

### Version metadata
ipocket includes build metadata in `/health` and in the sidebar footer in the UI
(including signed-out pages that render the sidebar).
The sidebar renders the version value as-is (for example: `ipocket dev (abc1234)`).

In Docker, if no version env vars are provided, ipocket attempts to detect commit
from the embedded `.git` metadata and uses a Docker-friendly fallback version
format: `sha-{short_commit}`.

- `IPOCKET_VERSION` (semantic version, e.g. `0.1.0`)
- `IPOCKET_COMMIT` (git commit SHA, short ok)
- `IPOCKET_BUILD_TIME` (ISO timestamp)
- `IPOCKET_DOCKER_TAG` (optional; if set and running in Docker, replaces `IPOCKET_VERSION` with the image tag)
- `IPOCKET_DOCKER_RUNTIME` (optional; set to `1`/`true` to force Docker detection for `IPOCKET_DOCKER_TAG`)

Example `docker-compose.yml` snippet:

```yaml
services:
  ipocket:
    image: ipocket:latest
    environment:
      IPOCKET_VERSION: "0.1.0"
      IPOCKET_COMMIT: "abc1234"
      IPOCKET_BUILD_TIME: "2024-01-01T00:00:00Z"
```


Service discovery token (optional):
- `IPOCKET_SD_TOKEN` (when set, `/sd/node` requires header `X-SD-Token`)
- `IPOCKET_AUTO_HOST_FOR_BMC` (default: enabled). Set to `0`, `false`, `no`, or `off` to disable auto-creating `server_{ip}` Host records when creating BMC IP assets without `host_id` and to disable the BMC Detail auto-host action.
- `IPOCKET_LOG_LEVEL` (default: `INFO`). Controls application logging verbosity (e.g., `DEBUG`, `INFO`, `WARNING`).

Session security:
- `SESSION_SECRET` (required outside tests). UI session/flash cookies are HMAC-signed, and startup now raises `RuntimeError` if this variable is missing or blank in non-testing environments.
- During automated tests, ipocket uses an internal test-only fallback secret so test runs do not require extra env setup.

Example systemd unit override (`Environment=`):

```ini
[Service]
Environment="IPOCKET_VERSION=0.1.0"
Environment="IPOCKET_COMMIT=abc1234"
Environment="IPOCKET_BUILD_TIME=2024-01-01T00:00:00Z"
Environment="SESSION_SECRET=replace-with-random-long-secret"
```

Endpoints:
- Health check: http://127.0.0.1:8000/health
- Metrics: http://127.0.0.1:8000/metrics
- Service discovery: http://127.0.0.1:8000/sd/node

Connector CLI examples:
- Cassandra node import: `python -m app.connectors.cassandra --contact-points 10.0.0.10,10.0.0.11 --mode dry-run --db-path ./ipocket.db`
- Ceph host import: `python -m app.connectors.ceph --ceph-url https://ceph-mgr.example.local:8443 --username admin --password '<password>' --mode dry-run --db-path ./ipocket.db`
- Kubernetes node import: `python -m app.connectors.kubernetes --api-url https://kubernetes.example.local:6443 --token '<service-account-token>' --mode dry-run --db-path ./ipocket.db`
- Full Cassandra connector options are documented in `/docs/cassandra-connector.md`.
- Full Ceph connector options are documented in `/docs/ceph-connector.md`.
- Full Kubernetes connector options are documented in `/docs/kubernetes-connector.md`.

## UI login (browser)
Bootstrap a local Superuser before startup:

```bash
export ADMIN_BOOTSTRAP_USERNAME=admin
export ADMIN_BOOTSTRAP_PASSWORD=admin-pass
```

Start the app and sign in:
- Visit http://127.0.0.1:8000/ui/login
- Login with the bootstrap credentials.
- The login page is React-powered and uses `POST /api/ui/login`; its Jinja shell intentionally omits the application sidebar/navigation.
- Authentication policy remains server-side: username normalization, password verification, inactive-user rejection, generic failure messages, approved return URLs, session creation, and signed `ipocket_session` cookie handling are not implemented in the browser.
- The legacy form-compatible `POST /ui/login` endpoint remains available and uses the same server-side authentication/session helper as the JSON endpoint.
- Passwords are stored as bcrypt hashes (`passlib`); successful login also upgrades any legacy SHA-256 password hashes.
- API/UI login sessions are stored in the SQLite `sessions` table, so tokens remain valid across app restarts until logout or token revocation.
- Editors can add or edit IPs from the UI.
- Editors and Superusers can maintain Projects, Vendors, and Tags from the Library page; Viewers see the catalog without mutation controls.
- Any authenticated user (Viewer/Editor/Superuser) can change their own password on the React-powered page at `http://127.0.0.1:8000/ui/account/password` by entering current password + new password (with confirmation). Password verification, hashing, and USER audit logging remain server-side; the page never receives a password hash.

## User management
User management requires the bootstrap superuser env vars.

### UI user management
After logging in as superuser, open:

```bash
http://127.0.0.1:8000/ui/users
```

This React-powered page is restricted to Superusers and supports:
- creating users
- granting/revoking edit access
- activating/deactivating users
- rotating user passwords
- deleting users (with confirmation)

Safety rules:
- Viewer and Editor accounts cannot open the page or call its management API
- managed accounts can be Viewer or Editor; User Management cannot grant or remove Superuser access
- passwords are hashed on the server and are never returned by the management API
- empty password fields during edit leave the current password unchanged
- a user cannot delete their own account
- the last active superuser cannot be deactivated
- the last active superuser cannot be deleted
- user-related audit logs are retained when a user is deleted
- CREATE, changed UPDATE, and DELETE operations write USER audit entries; no-op edits do not

The legacy direct form routes under `/ui/users` remain available for existing
links and tests, and share the same backend validation and mutation helpers as
the JSON API.

UI design reference templates live in `/ui_template` for layout and styling guidance.

## First-time setup checklist
1) Bootstrap a superuser (env vars above).
2) Login at `/ui/login`.
3) Open **Library** from the sidebar and use tabs to create Projects, Tags, and Vendors.
   - The header **New Project / New Tag / New Vendor** button opens the matching create drawer for the active tab.
4) In **Library → Tags**, the create drawer now suggests a random color by default; you can keep it or pick another color before saving.
5) Create Hosts from the **Hosts** page and pick a Vendor when needed. Use the React search panel to filter by text, Vendor, Project, Assignment, linked/free Status, or tags from linked active IPs. Filters and pagination stay in the URL, back/forward navigation restores them, and changes refresh the table without reloading the shell. Pagination controls are integrated into the table footer, which shows the visible row range and total alongside rows-per-page and previous/next controls. The OS IPs and BMC IPs columns link directly to each address detail page, and the **IP tags** column shows deduplicated tags from linked active IP assets (not host-level tags), with only the first 2 shown inline and the rest available through a searchable `+N more` popover anchored to that row; hover, focus, or click opens it. Clicking any shown tag applies it as a Hosts tag filter. Create/edit/delete runs in the right-side drawer; focus remains in the field being edited while controlled values update. Deleting requires acknowledgement plus the exact Host name and unlinks rather than deletes IP assets. Open a Host name to use the unchanged Host detail page.
6) Add IPs from the **IP Assets** page. In IP create/edit forms, use the searchable Host combobox to filter large host lists and select the host from the same control before assigning OS/BMC addresses. The IP Assets Tags filter has three chip groups: **OR** matches one or more selected tags (`prod` or `edge`), **AND** requires every selected tag (`prod` and `edge`), and **NOT** hides IPs with selected tags such as `deprecated`. Clicking a tag chip in the table adds it to the active group; older URLs using repeated `tag=...` still behave as OR filters.
7) When you paginate in **IP Assets**, edits from the drawer return you to the same filtered/paginated list state (current `page` and `per-page` are preserved).
8) Open **Data Ops** from the sidebar to import or export data using one unified page with tabs. `hosts.csv` exports now include `project_name`, `os_ip`, and `bmc_ip` for round-trip compatibility with CSV import.
   `ip-assets.csv` exports are sorted by numeric IP order (for example `10.0.0.2` appears before `10.0.0.10`), including legacy rows where `ip_int` is null.
   Import upload guardrails: each uploaded file (`bundle.json`, CSV, Nmap XML) is limited to `10 MB`; oversize files are rejected with HTTP `413`.
9) Open **Connectors** from the sidebar and use **vCenter**, **Prometheus**, **Elasticsearch**, **Cassandra**, **Ceph**, or **Kubernetes** tabs to run connectors directly from UI (`dry-run` or `apply`) as background jobs; while a run is queued/running, the tab auto-refreshes (same `job_id` URL) to show final status and logs without manual refresh.
10) When assigning tags on IP Assets or Range Address drawers, use the chip picker (`Add tags...`) to search and select existing tags only (create new tag names first in **Library → Tags**).
11) For multi-row assignment changes, select IPs in **IP Assets** and use **Bulk update** to open the right-side drawer for batch Type/Project/Tag updates; shared tags appear under **Common tags** and can be removed for all selected rows in one apply. For notes, use **Notes action**: keep current notes, overwrite with a provided value, or clear notes for all selected rows.
12) On an IP Asset detail page, use the React **Edit** and **Delete** drawers without reloading the shell. Edit refreshes Detail and Audit Log after success. Delete requires acknowledgement, plus exact-IP typing for high-risk records, and returns to the IP Assets list. An unassigned BMC also offers **Create host** when `IPOCKET_AUTO_HOST_FOR_BMC` is enabled.
13) On an OS or BMC IP Asset detail page, use the Details panel to see the paired address from the same host: OS records show BMC addresses, and BMC records show OS addresses. The IP address, Host, and paired OS/BMC address values link directly to their detail pages. Other asset types do not show the paired-address field.
14) Open **Audit Log** to review run-level `apply` entries for Data Ops and Connectors (`IMPORT_RUN`); dry-run executions are intentionally excluded from run-level audit logging.
15) On the React-powered range details page (`/ui/ranges/<id>/addresses`), use separate filters for **IP address** (500 ms live search), **Project**, **Type**, and chip-based **Tags**, plus **Status** (`All/Used/Free`) and table pagination controls (`Rows`, `Previous`, `Next`). Filter state is shareable in the URL and restored by Back/Forward. Tag cells show up to 3 tags inline and collapse the rest into a searchable `+N more` popover; clicking any tag applies it to the active filter. Editors can allocate a free address or edit a used address in the right-side drawer; Viewers see no mutation controls. Example: `/ui/ranges/1/addresses?project_id=unassigned&type=BMC&tag=mgmt&status=used`.

Assignment workflow note: use **IP Assets → Assignment = Unassigned only** to review and update records that still need a project. You can also use **Project = Unassigned** in the search filters for the same project-missing view. The old dedicated **Needs Assignment** page is removed.
Notification note: IP Assets bulk/update/delete actions clear stale `bulk-error` / `bulk-success` / `delete-error` / `delete-success` URL query values before redirecting, so old toasts do not persist into later actions.

## Example API calls
Login and capture a token:

```bash
curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"editor","password":"editor-pass"}'
```

Create an IP asset (Editor):

```bash
curl -s -X POST http://127.0.0.1:8000/ip-assets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"ip_address":"10.0.0.50","type":"VM"}'
```

If `10.0.0.50` already exists only as an archived IP, the create call restores that archived record instead of returning a duplicate conflict.

List unassigned IPs:

```bash
curl -s "http://127.0.0.1:8000/ip-assets?unassigned-only=true"
```

Delete an IP asset (Editor):

```bash
curl -s -X DELETE http://127.0.0.1:8000/ip-assets/10.0.0.50 \
  -H "Authorization: Bearer <token>"
```

UI safety flow: deleting an IP from UI requires opening the delete confirmation page and typing the exact IP address in a textbox before the permanent delete is accepted.

Host UI safety flow: deleting a Host from UI requires opening the host delete confirmation page and typing the exact host name; deletion is blocked when IPs are still linked to that host.

## Run tests
```bash
.venv/bin/pytest -q
```

## Developer code map (UI routes)
- Aggregated UI router entrypoint: `app/routes/ui/__init__.py`
- IP assets routes: `app/routes/ui/ip_assets/` (`listing.py`, `forms.py`, `actions.py`, `helpers.py`)
- Hosts routes: `app/routes/ui/hosts/` (`api.py`, `listing.py`, `mutations.py`, `detail.py`)
- Ranges routes: `app/routes/ui/ranges/` (`crud.py`, `addresses.py`, `common.py`)
- Library/settings routes: `app/routes/ui/settings/` (`api.py`, `projects.py`, `tags.py`, `vendors.py`, `audit.py`, `common.py`)

## Manual vCenter export connector

To export ESXi hosts and VMs from vCenter into an importable ipocket bundle, use:

```bash
python -m app.connectors.vcenter --server <vcenter> --username <user> --password '<pass>' --output ./vcenter-bundle.json
```

Then import the generated JSON from **Data Ops → Import**.

You can also open **Connectors → vCenter** in the UI for the same command examples.
The UI flow also supports direct execution:

- Fill vCenter server/username/password (and optional TLS-skip + custom port)
- Choose mode:
  - `dry-run` (recommended first)
  - `apply`
- Click **Run Connector** (the run is queued in background)
- Keep the connector tab open/refresh to review job status and execution logs for collected host/VM counts and any warnings/errors

To skip manual upload and send directly to ipocket import API:

```bash
python -m app.connectors.vcenter --server <vcenter> --username <user> --password '<pass>' --mode dry-run --ipocket-url http://127.0.0.1:8000 --token '<token>'
```

See `/docs/vcenter-connector.md` for full mapping and options.

Update semantics for existing IP assets (apply mode):
- `type` is always overwritten from connector output.
- Connector tags are merged with existing tags (not full replacement).
- Connector notes are only applied when the existing note is empty.

## Prometheus connector (node_exporter / metric-driven import)

Use the Prometheus connector when you want to pull IPs from Prometheus query results
and import them as IP assets.

Note: Prometheus connector updates preserve non-empty existing IP notes (manual notes are not overwritten) and keep the existing `type` for records that are updated.

UI flow:
- Open **Connectors → Prometheus**
- Fill:
  - Prometheus URL
  - PromQL query (example: `up{job="node"}`)
  - IP label (for node_exporter usually `instance`)
  - optional auth (Bearer token or `username:password`)
  - optional project/tags/type override
- Start with `dry-run`, inspect extracted IP preview + per-IP change details (`CREATE`/`UPDATE`/`SKIP` with field diffs) + `ip_assets` create/update/skip summary in logs (from the background job result), then run `apply`.

CLI examples:

Write bundle file only:

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --asset-type OTHER \
  --mode file \
  --output ./prometheus-bundle.json
```

Direct dry-run into ipocket API:

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --token 'prom_user:prom_pass' \
  --mode dry-run \
  --ipocket-url http://127.0.0.1:8000 \
  --ipocket-token '<token>'
```

Direct apply into ipocket API:

```bash
python -m app.connectors.prometheus \
  --prometheus-url http://127.0.0.1:9090 \
  --query 'up{job="node"}' \
  --ip-label instance \
  --mode apply \
  --ipocket-url http://127.0.0.1:8000 \
  --ipocket-token '<token>'
```

See `/docs/prometheus-connector.md` for full options and edge-case behavior.

## Elasticsearch connector (node inventory import)

Use the Elasticsearch connector when you want to import IPv4 node addresses from
Elasticsearch cluster inventory (`/_nodes/http,transport`) into IP assets.

Notes:
- Authentication is optional. If required by your Elasticsearch deployment, use either `api_key` (Base64 or `id:key`) or `username/password`.
- TLS certificate verification is skipped by default and has no toggle.
- Existing IP updates can overwrite `type` and `project` (when provided), append
  tags, and overwrite note only when `note` is provided in the connector run.
- Optional cluster-name tagging adds the top-level Elasticsearch `cluster_name`
  as a normalized tag on every imported node IP.

UI flow:
- Open **Connectors → Elasticsearch**
- Fill:
  - Elasticsearch URL
  - optional auth: API key OR username/password
  - optional `type` / `project` / `tags` / `note`
  - optional **Add cluster name as tag**
- Start with `dry-run`, inspect logs, then run `apply`.

CLI examples:

Write bundle file only:

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --api-key '<base64-or-id:key>' \
  --asset-type OTHER \
  --mode file \
  --output ./elasticsearch-bundle.json
```

Direct dry-run into local DB:

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --username elastic \
  --password '<password>' \
  --tags elasticsearch,nodes \
  --include-cluster-name-tag \
  --mode dry-run \
  --db-path ./ipocket.db
```

Direct apply into local DB:

```bash
python -m app.connectors.elasticsearch \
  --elasticsearch-url https://127.0.0.1:9200 \
  --api-key '<base64-or-id:key>' \
  --project-name Core \
  --note 'Imported from Elasticsearch nodes' \
  --mode apply \
  --db-path ./ipocket.db
```

See `/docs/elasticsearch-connector.md` for full options and mapping details.

## Ceph connector (Dashboard host inventory import)

Use the Ceph connector when you want to import IPv4 host addresses from Ceph
Dashboard host inventory (`GET /api/host`) into IP assets and link them to
ipocket Hosts.

Notes:
- The connector authenticates with `POST /api/auth` and uses the returned JWT
  for host inventory requests.
- Existing IP updates can overwrite `type`, `project`, and host link, append
  tags, and overwrite note only when `note` is provided in the connector run.
- Optional cluster-name and label tagging add normalized tags to imported IPs.

UI flow:
- Open **Connectors → Ceph**.
- Fill:
  - Ceph Dashboard URL
  - username/password
  - optional `type` / `project` / `tags` / `note`
  - optional **Add cluster name as tag** or **Add Ceph labels as tags**
- Start with `dry-run`, inspect logs, then run `apply`.

CLI examples:

Write bundle file only:

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --asset-type OTHER \
  --mode file \
  --output ./ceph-bundle.json
```

Direct dry-run into local DB:

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --insecure \
  --tags ceph,nodes \
  --include-label-tags \
  --mode dry-run \
  --db-path ./ipocket.db
```

Direct apply into local DB:

```bash
python -m app.connectors.ceph \
  --ceph-url https://ceph-mgr.example.local:8443 \
  --username admin \
  --password '<password>' \
  --project-name Storage \
  --note 'Imported from Ceph Dashboard hosts' \
  --mode apply \
  --db-path ./ipocket.db
```

See `/docs/ceph-connector.md` for full options and mapping details.

## Kubernetes connector (Node InternalIP import)

Use the Kubernetes connector when you want to import Kubernetes node InternalIP
addresses into ipocket and link each address to a Host named from the Kubernetes
Node.

- Open **Connectors → Kubernetes**.
- Fill Kubernetes API URL and bearer token.
- Set optional mapping fields (`type/project/tags/note`) and optional
  cluster/label tag options.
- Run **dry-run** first, then **apply** as an editor account.

CLI example:

```bash
python -m app.connectors.kubernetes \
  --api-url https://kubernetes.example.local:6443 \
  --token '<service-account-token>' \
  --asset-type OS \
  --include-label-tags \
  --mode dry-run \
  --db-path ./ipocket.db
```

See `/docs/kubernetes-connector.md` for full options and mapping details.

## CI (quality + full tests)
The GitHub Actions workflow runs code quality checks and the full pytest suite
on each pull request and push to `main`.

Quality job:

```bash
ruff check .
ruff format --check .
```

Test job:

```bash
pytest tests --cov=app --cov-fail-under=75
```

## Docker Hub release automation
When a Git tag that starts with `v` is pushed (for example, `v0.2.0`), the CI
workflow builds the Docker image and pushes it to Docker Hub as both the version
tag and `latest`.

Required GitHub secrets:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`


## Test suite layout

Tests now mirror the application modules:

- `tests/repository/` for repository/data-layer unit tests.
- `tests/ui/` for UI router/page tests.
- `tests/ui/test_connectors.py` covers the composed connector router plus the focused modules under `app/routes/ui/connector_routes/`.
- `tests/api/` for API route and auth/permission tests.
- `tests/conftest.py` provides shared fixtures/helpers (`client`, `_setup_connection`, `_setup_session`, `_create_user`, `_login`, `_auth_headers`).

Run subsets as needed, for example:

```bash
pytest tests/repository -q
pytest tests/ui -q
pytest tests/ui/test_connectors.py -q
pytest tests/api -q
```
