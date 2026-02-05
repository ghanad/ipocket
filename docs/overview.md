# Overview

ipocket is a lightweight, modular IP inventory web app with a UI aligned to the design reference in `/ui_template` and Prometheus metrics.

UI templates live in `app/templates`, UI routes live in `app/routes/ui.py`, and static assets are served from `app/static`.

## MVP Goals
- Store IP records with metadata (type required; subnet/gateway optional).
- Use `BMC` as the vendor-neutral management interface type (covers iLO/iDRAC/IPMI).
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
- `GET /sd/node`: Prometheus HTTP service discovery target groups for non-archived IPs (supports `port`, `only_assigned`, `project`, `owner`, and `type` filters, plus `group_by` output grouping).

## UI Pages (MVP)
- `GET /ui/login`: browser login form.
- `GET /ui/ip-assets`: IP list with search and filters (project, owner, type, unassigned-only). Empty filter selections are ignored. The table intentionally omits the Subnet column to keep the list focused on assignment status.
- `GET /ui/ip-assets/needs-assignment`: dedicated view to focus on IPs missing Owner and/or Project, with tabs for Needs Owner, Needs Project, and Needs Both.
- `GET /ui/ip-assets/{asset_id}`: IP detail page with assignment status.
- `GET /ui/ip-assets/new`: add IP form (Editor/Admin). Subnet and Gateway are optional when creating an IP.
- `GET /ui/ip-assets/{asset_id}/edit`: edit IP form (Editor/Admin). Subnet and Gateway are optional when editing an IP as well.
- `GET /ui/projects`: list/create projects and inline-edit existing rows (Editor/Admin write access). The Existing projects table header has internal padding to keep content off card edges for better readability.
- `GET /ui/owners`: list/create owners and inline-edit existing rows (Editor/Admin write access). The Existing owners table header uses the same internal padding treatment for consistent spacing.
- `GET /ui/ip-assets/needs-assignment`: matching IPs table header uses the same padded card-header layout for consistent spacing.
- `POST /ui/ip-assets/{asset_id}/archive`: archive action (Editor/Admin).
- `POST /ui/logout`: clear the UI session. The sidebar logout action uses the same navigation button styling for consistent visual alignment.
- Authenticated pages no longer render the legacy bottom copyright footer.


## Assignment workflow (MVP)
- Use the **Needs Assignment** page to filter IPs missing Owner and/or Project.
- Editors/Admins can use the Quick Assign form to select an IP and set Owner and/or Project in one action.
- Viewers can browse the page but will receive a 403 if they attempt assignments.

## How to use the UI
1. Log in at `/ui/login` using an Editor or Admin account.
2. Visit **Projects** to add project names (e.g., Core, Payments) or update existing project names/descriptions inline from the table.
3. Visit **Owners** to add responsible teams or contacts, or update existing owner names/contacts inline from the table.
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


## Additional docs
- Service discovery endpoint docs: `/docs/service-discovery.md`.
