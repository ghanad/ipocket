# ipocket

**ipocket** is a lightweight, modular IP inventory web app (mini IPAM) with a FastAPI backend, SQLite storage, and Prometheus-friendly observability.

## Current Scope (Post-MVP)
The project is now beyond MVP and includes a broader operational workflow:
- IP asset inventory with project-based assignment workflows
- Host, vendor, tag, and IP range management
- Import/export data operations (CSV, JSON, bundle, Nmap XML)
- Connector-driven ingestion (vCenter and Prometheus)
- Management dashboard, audit logging, and service discovery endpoint
- Prometheus metrics at `GET /metrics`

## Core Capabilities
- IP assets CRUD with soft-delete (`archived`) and fast filtering/search
- Assignment workflow integrated directly in the IP Assets list (`Unassigned only`)
- Catalog management in Library tabs (Projects, Tags, Vendors)
- Host workflows with OS/BMC linkage and vendor assignment
- CIDR range tracking and address utilization drill-down
- Unified Data Ops page for import/export
- Connector runs from UI and CLI (`dry-run` / `apply`)
- Audit trail for inventory and user-management actions

## Data Model (High-Level)
Main entities:
- `IPAsset` (`ip_address`, `type`, `project`, `host`, `tags`, `notes`, `archived`, timestamps)
- `Project`
- `Host`
- `Vendor`
- `Tag`
- `IPRange`
- `User`
- `AuditLog`

For exact fields and constraints see: `docs/data-model.md`.

## Prometheus Metrics
`GET /metrics` exposes:
- `ipam_ip_total`
- `ipam_ip_archived_total`
- `ipam_ip_unassigned_owner_total`
- `ipam_ip_unassigned_project_total`
- `ipam_ip_unassigned_both_total`

Details: `docs/metrics.md`.

## Quick Start
### Local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open:
- UI login: `http://127.0.0.1:8000/ui/login`
- Health: `http://127.0.0.1:8000/health`
- Metrics: `http://127.0.0.1:8000/metrics`

For Docker/Compose, env vars, and full setup, see `docs/how-to-run.md`.

## Documentation Map
- Product overview: `docs/overview.md`
- Data model: `docs/data-model.md`
- Metrics: `docs/metrics.md`
- Run and operations: `docs/how-to-run.md`
- Export/import: `docs/export-import.md`
- Service discovery: `docs/service-discovery.md`
- Connectors:
  - `docs/vcenter-connector.md`
  - `docs/prometheus-connector.md`

## Contributing
Read `AGENTS.md` before making changes.

Mandatory project rules:
- Every code change must include unit tests.
- Every feature must be documented in `/docs`.
- Keep implementations simple and modular.
