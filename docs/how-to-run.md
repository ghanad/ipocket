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

### Version metadata (recommended for deployments)
ipocket reads version info from environment variables and includes them in the
`/health` response and the authenticated UI footer (`ipocket v{version} ({commit}) • built {build_time}`).
When unset, defaults are shown as `dev/unknown`.

- `IPOCKET_VERSION` (semantic version, e.g. `0.1.0`)
- `IPOCKET_COMMIT` (git commit SHA, short ok)
- `IPOCKET_BUILD_TIME` (ISO timestamp)

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
Bootstrap a local Admin user before startup:

```bash
export ADMIN_BOOTSTRAP_USERNAME=admin
export ADMIN_BOOTSTRAP_PASSWORD=admin-pass
```

Start the app and sign in:
- Visit http://127.0.0.1:8000/ui/login
- Login with the bootstrap credentials.
- Editors/Admins can add or edit IPs from the UI.

UI design reference templates live in `/ui_template` for layout and styling guidance.

## First-time setup checklist
1) Bootstrap an admin user (env vars above).
2) Login at `/ui/login`.
3) Create Projects from the **Projects** page.
4) Create Vendors from the **Vendors** page.
5) Create Hosts from the **Hosts** page and pick a Vendor when needed.
6) Add IPs from the **IP Assets** page.

## Example API calls
Login and capture a token:

```bash
curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"editor","password":"editor-pass"}'
```

Create an IP asset (Editor/Admin):

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

Delete an IP asset (Editor/Admin):

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
