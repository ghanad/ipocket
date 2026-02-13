# ipocket — AGENTS.md

You are an AI coding agent contributing to **ipocket** (a lightweight, modular IP inventory web app with Prometheus metrics).

## Golden Rules (MUST)
1) **Every code change MUST include unit tests**.
   - New features require new/updated tests.
   - Bug fixes require regression tests.
   - Changes without tests are not acceptable.

2) **Every feature/change MUST be documented in `/docs`**.
   - Add or update practical docs for behavior, usage, and operational impact.
   - Keep docs short, accurate, and aligned with current implementation.

3) Keep it **simple and modular**.
   - Prefer focused modules over large files.
   - Preserve clean boundaries for future expansion.

## Product Scope (Current)
ipocket is beyond MVP and currently includes:
- IP asset inventory (CRUD + archive + filtering/search)
- Project-based assignment workflows in the IP Assets list
- Hosts, vendors, tags, and IP ranges management
- Import/export workflows (bundle, CSV, Nmap XML)
- Connector-driven ingestion (vCenter, Prometheus)
- Audit logs and management dashboard
- Prometheus metrics at `GET /metrics`
- Prometheus HTTP service discovery at `GET /sd/node`

## Core Data (Current)
IP assets and related entities currently cover:
- `ip_address` (unique)
- `project` (nullable)
- `type` (`OS`, `BMC`, `VM`, `VIP`, `OTHER`)
- `host` (nullable)
- `tags` (many-to-many)
- `notes` (optional)
- timestamps
- `archived` flag (soft delete)

Supporting entities include `Project`, `Host`, `Vendor`, `Tag`, `IPRange`, `User`, and `AuditLog`.

Note: owner support is currently paused in implementation; keep compatibility where needed (for existing metrics and API expectations).

## Prometheus Metrics (Required)
Keep `/metrics` exposing at least:
- `ipam_ip_total`
- `ipam_ip_archived_total`
- `ipam_ip_unassigned_owner_total`
- `ipam_ip_unassigned_project_total`
- `ipam_ip_unassigned_both_total`

## UI Behavior (Current)
- IP Assets list is the primary assignment workflow.
- Use `Assignment = Unassigned only` and `Project = Unassigned` filters for project-missing review.
- There is **no dedicated "Needs Assignment" page** in the current UI.
- Editing flows should stay low-click and consistent with drawer-based UI patterns.

## Documentation Rules (`/docs`)
Always keep these docs current when behavior changes:
- `/docs/overview.md`
- `/docs/data-model.md`
- `/docs/metrics.md`
- `/docs/how-to-run.md`

Update feature-specific docs as relevant, including:
- `/docs/export-import.md`
- `/docs/service-discovery.md`
- `/docs/vcenter-connector.md`
- `/docs/prometheus-connector.md`

## Testing Rules
- Default to unit tests (fast, deterministic, isolated).
- Add or update tests for impacted modules (repository, API routes, UI routes/helpers, import/export, connectors).
- Ensure coverage for:
  - IP record create/update/archive behavior
  - assignment and unassigned counts
  - `/metrics` payload correctness
  - behavior changes introduced by your patch
- No real external network calls in tests.

## If anything is unclear
- Choose the simplest implementation that keeps extension paths open.
- Add short TODO notes only when truly necessary.
- If behavior changes, mirror it in docs in the same change set.
