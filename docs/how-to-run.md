# How to run

## Requirements
- Python 3.11+
- SQLite (built-in)
- HTTP client support comes from the pip-installed `httpx` package in `requirements.txt`; ipocket does not ship a local `httpx/` package in the repo to avoid import shadowing.

## Run locally
Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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

## Offline environments
Docker deployments default to local/static assets (CSS + JS like htmx) so the UI
renders without downloading from public CDNs. Non-Docker runs will load the
Inter font from Google Fonts and htmx/Alpine.js from CDNs by default. Library
Projects, Tags, and Vendors drawers are Alpine-driven in the Jinja templates, and the Tags
create drawer auto-suggests a random color when not prefilled. In local asset mode
(`IPOCKET_DOCKER_ASSETS=1`), Library drawer interactivity falls back to local scripts
(`/static/js/projects.js`, `/static/js/tags.js`, `/static/js/vendors.js`, and
`/static/js/drawer.js`) so all Library tab drawer actions stay available offline.
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
- `IPOCKET_AUTO_HOST_FOR_BMC` (default: enabled). Set to `0`, `false`, `no`, or `off` to disable auto-creating `server_{ip}` Host records when creating BMC IP assets without `host_id`.
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

## UI login (browser)
Bootstrap a local Superuser before startup:

```bash
export ADMIN_BOOTSTRAP_USERNAME=admin
export ADMIN_BOOTSTRAP_PASSWORD=admin-pass
```

Start the app and sign in:
- Visit http://127.0.0.1:8000/ui/login
- Login with the bootstrap credentials.
- Passwords are stored as bcrypt hashes (`passlib`); successful login also upgrades any legacy SHA-256 password hashes.
- API/UI login sessions are stored in the SQLite `sessions` table, so tokens remain valid across app restarts until logout or token revocation.
- Editors can add or edit IPs from the UI.
- Any authenticated user (Viewer/Editor/Superuser) can change their own password at `http://127.0.0.1:8000/ui/account/password` by entering current password + new password (with confirmation).

## User management
User management requires the bootstrap superuser env vars.

### UI user management
After logging in as superuser, open:

```bash
http://127.0.0.1:8000/ui/users
```

This page is restricted to superusers and supports:
- creating users
- granting/revoking edit access
- activating/deactivating users
- rotating user passwords
- deleting users (with confirmation)

Safety rules:
- the last active superuser cannot be deleted
- user-related audit logs are retained when a user is deleted

UI design reference templates live in `/ui_template` for layout and styling guidance.

## First-time setup checklist
1) Bootstrap a superuser (env vars above).
2) Login at `/ui/login`.
3) Open **Library** from the sidebar and use tabs to create Projects, Tags, and Vendors.
   - The header **New Project / New Tag / New Vendor** button opens the matching create drawer for the active tab.
4) In **Library → Tags**, the create drawer now suggests a random color by default; you can keep it or pick another color before saving.
5) Create Hosts from the **Hosts** page and pick a Vendor when needed.
6) Add IPs from the **IP Assets** page.
7) When you paginate in **IP Assets**, edits from the drawer return you to the same filtered/paginated list state (current `page` and `per-page` are preserved).
8) Open **Data Ops** from the sidebar to import or export data using one unified page with tabs. `hosts.csv` exports now include `project_name`, `os_ip`, and `bmc_ip` for round-trip compatibility with CSV import.
   Import upload guardrails: each uploaded file (`bundle.json`, CSV, Nmap XML) is limited to `10 MB`; oversize files are rejected with HTTP `413`.
9) Open **Connectors** from the sidebar and use **vCenter** or **Prometheus** tabs to run connectors directly from UI (`dry-run` or `apply`) as background jobs, then refresh the tab URL (with `job_id`) to review status and execution logs.
10) When assigning tags on IP Assets or Range Address drawers, use the chip picker (`Add tags...`) to search and select existing tags only (create new tag names first in **Library → Tags**).
11) For multi-row assignment changes, select IPs in **IP Assets** and use **Bulk update** to open the right-side drawer for batch Type/Project/Tag updates; shared tags appear under **Common tags** and can be removed for all selected rows in one apply.
12) Open **Audit Log** to review run-level `apply` entries for Data Ops and Connectors (`IMPORT_RUN`); dry-run executions are intentionally excluded from run-level audit logging.
13) On a range details page (`/ui/ranges/<id>/addresses`), use separate filters for **IP address** (live search), **Project**, **Type**, and chip-based **Tags** (same Enter/add/remove flow as IP Assets), plus **Status** (`All/Used/Free`) and table pagination controls (`Rows`, `Previous`, `Next`) to review large ranges efficiently. In the table, tag cells show up to 3 tags inline and collapse the rest into a `+N more` popover; clicking a tag chip (inline or popover) adds that tag directly to the active Tags filter. Example: `/ui/ranges/1/addresses?project_id=unassigned&type=BMC&tag=mgmt&status=used`.

Assignment workflow note: use **IP Assets → Assignment = Unassigned only** to review and update records that still need a project. You can also use **Project = Unassigned** in the search filters for the same project-missing view. The old dedicated **Needs Assignment** page is removed.

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
- Hosts routes: `app/routes/ui/hosts/` (`listing.py`, `mutations.py`, `detail.py`)
- Ranges routes: `app/routes/ui/ranges/` (`crud.py`, `addresses.py`, `common.py`)
- Library/settings routes: `app/routes/ui/settings/` (`projects.py`, `tags.py`, `vendors.py`, `audit.py`, `common.py`)

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
- `tests/api/` for API route and auth/permission tests.
- `tests/conftest.py` provides shared fixtures/helpers (`client`, `_setup_connection`, `_setup_session`, `_create_user`, `_login`, `_auth_headers`).

Run subsets as needed, for example:

```bash
pytest tests/repository -q
pytest tests/ui -q
pytest tests/api -q
```
