# Overview

ipocket is a lightweight, modular IP inventory web app with a simple UI and Prometheus metrics.

## MVP Goals
- Store IP records with metadata (subnet, gateway, type).
- Track ownership and project assignment.
- Make unassigned records highly visible.
- Provide Prometheus metrics for monitoring and alerting.

## Roles (MVP)
- Viewer: read-only access
- Editor: can create/update/archive records and assign Owner/Project
- Admin: same as Editor today (reserved for future user/system management)

## Authentication (MVP)
- Login via `POST /login` with username/password to receive a bearer token.
- Include `Authorization: Bearer <token>` on write requests (create/update/archive).

## API / Routes overview
- `GET /ip-assets`: list active IPs (filters: `project_id`, `owner_id`, `type`, `unassigned-only`).
- `POST /ip-assets`: create IP (Editor/Admin).
- `PATCH /ip-assets/{ip_address}`: update IP (Editor/Admin).
- `POST /ip-assets/{ip_address}/archive`: archive IP (Editor/Admin).
- `GET /ip-assets/{ip_address}`: get IP detail.
- `GET /projects`: list projects.
- `POST /projects`: create project (Editor/Admin).
- `PATCH /projects/{project_id}`: update project (Editor/Admin).
- `GET /owners`: list owners.
- `POST /owners`: create owner (Editor/Admin).
- `PATCH /owners/{owner_id}`: update owner (Editor/Admin).

## UI Pages (MVP)
- `GET /ui/ip-assets`: IP list with search and filters (project, owner, type, unassigned-only).
- `GET /ui/ip-assets/needs-assignment`: dedicated view to focus on IPs missing Owner and/or Project, with tabs for Needs Owner, Needs Project, and Needs Both.
- `GET /ui/ip-assets/{ip_address}`: IP detail page with assignment status.
- `GET /ui/ip-assets/new`: add IP form (Editor/Admin).
- `GET /ui/ip-assets/{ip_address}/edit`: edit IP form (Editor/Admin).
- `POST /ui/ip-assets/{ip_address}/archive`: archive action (Editor/Admin).

## Assignment workflow (MVP)
- Use the **Needs Assignment** page to filter IPs missing Owner and/or Project.
- Editors/Admins can use the Quick Assign form to select an IP and set Owner and/or Project in one action.
- Viewers can browse the page but will receive a 403 if they attempt assignments.

## Bootstrap Admin (local dev)
- Set `ADMIN_BOOTSTRAP_USERNAME` and `ADMIN_BOOTSTRAP_PASSWORD` before startup.
- The app creates the first Admin user only if the users table is empty.

## Future Phases (planned)
- Health checks (ping/80/443)
- Discovery/scanner (range scanning + NEW/GONE detection)
- Importers (CSV/API/DHCP/cloud)
- Notifications (Slack/Email)
