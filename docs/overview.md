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
- Browser UI uses session login at `GET /ui/login` and stores a signed cookie for Editor/Admin actions.

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
- `GET /ui/login`: browser login form.
- `GET /ui/ip-assets`: IP list with search and filters (project, owner, type, unassigned-only).
- `GET /ui/ip-assets/needs-assignment`: dedicated view to focus on IPs missing Owner and/or Project, with tabs for Needs Owner, Needs Project, and Needs Both.
- `GET /ui/ip-assets/{asset_id}`: IP detail page with assignment status.
- `GET /ui/ip-assets/new`: add IP form (Editor/Admin).
- `GET /ui/ip-assets/{asset_id}/edit`: edit IP form (Editor/Admin).
- `GET /ui/projects`: list/create projects (Editor/Admin create).
- `GET /ui/owners`: list/create owners (Editor/Admin create).
- `POST /ui/ip-assets/{asset_id}/archive`: archive action (Editor/Admin).
- `POST /ui/logout`: clear the UI session.

## Assignment workflow (MVP)
- Use the **Needs Assignment** page to filter IPs missing Owner and/or Project.
- Editors/Admins can use the Quick Assign form to select an IP and set Owner and/or Project in one action.
- Viewers can browse the page but will receive a 403 if they attempt assignments.

## How to use the UI
1. Log in at `/ui/login` using an Editor or Admin account.
2. Visit **Projects** to add project names (e.g., Core, Payments).
3. Visit **Owners** to add responsible teams or contacts.
4. Go to **IP Assets** and add new IPs, selecting a Project and Owner from the dropdowns (or leave unassigned).
5. Use **Needs Assignment** to find and fix missing Owner/Project assignments quickly.

## Bootstrap Admin (local dev)
- Set `ADMIN_BOOTSTRAP_USERNAME` and `ADMIN_BOOTSTRAP_PASSWORD` before startup.
- The app creates the first Admin user only if the users table is empty.

## Future Phases (planned)
- Health checks (ping/80/443)
- Discovery/scanner (range scanning + NEW/GONE detection)
- Importers (CSV/API/DHCP/cloud)
- Notifications (Slack/Email)
