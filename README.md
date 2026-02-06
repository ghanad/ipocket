# ipocket

**ipocket** is a lightweight, modular IP inventory web app (mini IPAM) with Prometheus metrics.

## Why ipocket?
We want a small, simple system (lighter than NetBox) to:
- store IP addresses and their metadata
- track **Owner** and **Project** (critical!)
- highlight records that are missing Owner/Project
- export **Prometheus metrics** for monitoring/alerting

This repo is built for “vibe-coding”: AI agents should follow `AGENTS.md`.

---

## Phase 1 (MVP)
MVP scope:
- Web UI to view IPs (public read-only)
- Limited users can add/edit/archive IPs
- Data model: IPAsset, Project, Owner, User (roles)
- A dedicated view to quickly handle **Needs Assignment**:
  - needs owner
  - needs project
  - needs both
- Prometheus metrics at `GET /metrics`

Non-goals for MVP:
- no network scanning / discovery
- no continuous schedulers/jobs
- no complex multi-tenant RBAC

---

## Key Data (IPAsset)
Each IP record will support:
- `ip_address` (unique)
- `project` (may be empty in MVP)
- `owner` (may be empty in MVP)
- `type`: `VM | OS | BMC | VIP | OTHER`
- `notes` (optional)
- timestamps
- `archived` flag (soft delete)

---

## Prometheus Metrics (MVP minimum)
The `/metrics` endpoint must expose at least:
- `ipam_ip_total`
- `ipam_ip_archived_total`
- `ipam_ip_unassigned_owner_total`
- `ipam_ip_unassigned_project_total`
- `ipam_ip_unassigned_both_total`

See: `docs/metrics.md`

---

## Documentation
All documentation lives in `/docs`:
- `docs/overview.md`
- `docs/data-model.md`
- `docs/metrics.md`
- `docs/how-to-run.md`

Agents must update docs for every feature change.

---

## Contributing (AI Agents)
Read **`AGENTS.md`** first.
Golden rules:
- Every code change MUST include unit tests.
- Every feature MUST be documented in `/docs`.
- Keep it simple and modular.
