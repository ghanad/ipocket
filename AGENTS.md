# ipocket — AGENTS.md

You are an AI coding agent contributing to **ipocket** (a lightweight IP inventory web app with Prometheus metrics).

## Golden Rules (MUST)
1) **Every code change MUST include unit tests**.
   - If you add a feature, you MUST add/adjust tests for it.
   - If you fix a bug, you MUST add a regression test.
   - PRs without tests are not acceptable.

2) **Every feature MUST be documented in `/docs`**.
   - Add or update a short doc explaining what it does and how to use it.
   - Keep docs small, practical, and current.

3) Keep it **simple and modular**.
   - Prefer small modules over one big file.
   - Avoid over-engineering, but keep clean boundaries so future modules (scanner/importer/checker) can be added.

## What we are building (Phase 1 / MVP)
- A web app to store and view IP addresses + metadata.
- Limited users can add/edit; everyone can view.
- The app must highlight IPs that are missing **Owner** or **Project**.
- Expose Prometheus metrics at `GET /metrics`.

## Core Data (MVP)
Each IP record must support:
- ip_address (unique)
- subnet, gateway
- project (can be empty)
- owner (can be empty)
- type: VM / PHYSICAL / IPMI_ILO / VIP / OTHER
- notes (optional)
- timestamps
- archived flag (soft delete)

## Prometheus Metrics (MVP minimum)
Expose at least:
- `ipam_ip_total`
- `ipam_ip_archived_total`
- `ipam_ip_unassigned_owner_total`
- `ipam_ip_unassigned_project_total`
- `ipam_ip_unassigned_both_total`

## UI Behavior (MVP)
- A list page to browse/search/filter IPs (including "Unassigned only").
- A dedicated "Needs Assignment" view:
  - Needs Owner
  - Needs Project
  - Needs Both
- Editors/Admins can assign Owner/Project quickly (minimal clicks).

## Documentation Rules (`/docs`)
Maintain these docs (create if missing):
- `/docs/overview.md` (what is ipocket)
- `/docs/data-model.md` (fields + meaning)
- `/docs/metrics.md` (all Prometheus metrics + meanings)
- `/docs/how-to-run.md` (local run + tests)
Update these whenever behavior changes.

## Testing Rules
- Use unit tests as default (fast, isolated).
- Tests must cover:
  - creating IP records
  - assigning owner/project
  - "unassigned" counts
  - `/metrics` output includes correct numbers
- Keep tests deterministic (no real network calls).

## If anything is unclear
- Choose the simplest implementation that still allows future expansion.
- Leave TODO notes in code + add a short note in `/docs/overview.md`.
