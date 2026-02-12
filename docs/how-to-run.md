# How to run

## Requirements
- Python 3.11+
- SQLite (built-in)

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

The migration runner reads `IPAM_DB_PATH` (defaults to `ipocket.db`) to locate the
SQLite file.

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
Inter font from Google Fonts and htmx from a CDN by default. To force local
assets in any environment, set:

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

Example systemd unit override (`Environment=`):

```ini
[Service]
Environment="IPOCKET_VERSION=0.1.0"
Environment="IPOCKET_COMMIT=abc1234"
Environment="IPOCKET_BUILD_TIME=2024-01-01T00:00:00Z"
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
- Editors can add or edit IPs from the UI.

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
4) In **Library → Tags**, the create drawer now suggests a random color by default; you can keep it or pick another color before saving.
5) Create Hosts from the **Hosts** page and pick a Vendor when needed.
6) Add IPs from the **IP Assets** page.
7) Open **Data Ops** from the sidebar to import or export data using one unified page with tabs.
8) Open **Connectors** from the sidebar and use the **vCenter** tab to run the connector directly from UI (`dry-run` or `apply`) and review execution logs.
9) When assigning tags on IP Assets or Range Address drawers, use the chip picker (`Add tags...`) to search and select existing tags only (create new tag names first in **Library → Tags**).

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
pytest
```

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
- Click **Run Connector**
- Review the in-page execution log for collected host/VM counts and any warnings/errors

To skip manual upload and send directly to ipocket import API:

```bash
python -m app.connectors.vcenter --server <vcenter> --username <user> --password '<pass>' --mode dry-run --ipocket-url http://127.0.0.1:8000 --token '<token>'
```

See `/docs/vcenter-connector.md` for full mapping and options.

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
- `tests/conftest.py` provides shared fixtures/helpers (`client`, `_setup_connection`, `_create_user`, `_login`, `_auth_headers`).

Run subsets as needed, for example:

```bash
pytest tests/repository -q
pytest tests/ui -q
pytest tests/api -q
```
