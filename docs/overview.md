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

## Bootstrap Admin (local dev)
- Set `ADMIN_BOOTSTRAP_USERNAME` and `ADMIN_BOOTSTRAP_PASSWORD` before startup.
- The app creates the first Admin user only if the users table is empty.

## Future Phases (planned)
- Health checks (ping/80/443)
- Discovery/scanner (range scanning + NEW/GONE detection)
- Importers (CSV/API/DHCP/cloud)
- Notifications (Slack/Email)
