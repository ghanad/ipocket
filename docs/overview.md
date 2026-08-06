# ipocket overview

ipocket is a lightweight, modular IP inventory application with a React web UI,
FastAPI backend, SQLite storage, import connectors, audit logging, and Prometheus
integration.

## Frontend

The normal UI is implemented in React/Vite/TypeScript. FastAPI/Jinja provides
the shared HTML shell, navigation, session/flash context, and React mount points.
Focused `/api/ui/...` endpoints provide page data and mutations while enforcing
authorization on the server. See
[Frontend architecture](frontend-architecture.md) for the entry manifest,
generated-artifact policy, and retained compatibility boundary.

The primary pages are Management, IP Assets, Hosts, Ranges, Library, Connectors,
Audit Log, Data Operations, Users, Account Password, About, and the related
detail/login pages. List filters and pagination are URL-backed so browser
Back/Forward and shareable links preserve state.

## Inventory and assignment

- IP assets store a unique address, type (`OS`, `BMC`, `VM`, `VIP`, `OTHER`),
  optional Project and Host, tags, notes, timestamps, and an archive flag.
- The IP Assets list is the primary project-assignment workflow. Use **Project
  Assignment → Unassigned only** or **Project → Unassigned** to find missing
  project assignments; there is no separate Needs Assignment page.
- Search, project/type/assignment filters, OR/AND/NOT tag filters, numeric IP
  sorting, pagination, bulk edits, and archived-only URLs are supported.
- Editors use right-side drawers for create/edit/archive/delete and bulk Project,
  Tag, Type, and Notes changes. Destructive actions require acknowledgement and,
  for higher-risk records, exact-value confirmation.
- OS and BMC assets are paired through a shared Host. An unassigned BMC can
  create/reuse `server_<ip>` when `IPOCKET_AUTO_HOST_FOR_BMC` is enabled.

## Supporting catalogs

- Hosts group linked active IP assets into OS, BMC, and other addresses. Deleting
  a Host unlinks its IP assets rather than deleting them.
- Projects, Vendors, and Tags are managed from Library. Deleting a Project or
  Vendor clears the corresponding assignments; deleting a Tag removes its asset
  relationships.
- IPv4 CIDR ranges provide used/free utilization and a paginated address view
  with Project, Type, Tag, IP, and status filters.

## Data Operations and connectors

Data Operations supports bundle, CSV, and hardened Nmap XML import, dry-run/apply
preview, and native CSV/JSON/bundle downloads. Each uploaded file is limited to
10 MB. Viewers may dry-run; Apply requires Editor access.

Connectors for vCenter, Prometheus, Elasticsearch, Cassandra, Ceph, and
Kubernetes run as process-local background jobs. The UI polls job status and
keeps secrets out of bootstrap, job, log, and error payloads. Jobs expire after
one hour or a process restart. Connector-specific mapping and operational
details live in their focused documents under `docs/`.

## Authentication and audit

- Passwords use bcrypt through `passlib`; legacy SHA-256 hashes are upgraded on
  successful login.
- UI cookies and API bearer tokens resolve through persistent database sessions.
- Viewer is read-only, Editor can mutate inventory/catalog data and apply
  imports, and Superuser additionally manages users.
- IP Asset, User, and successful import/connector Apply operations create audit
  records. Dry-runs and no-op updates do not create run-level change entries.

## Operations

- `GET /health` returns application/build health metadata.
- `GET /metrics` exposes required IP inventory counters.
- `GET /sd/node` provides Prometheus HTTP service discovery.
- `GET /api/host-completion/analytics` summarizes active Host completeness,
  confirmed OS/BMC pairs, address-prefix patterns, and IP type counts without
  changing inventory.
- Docker, Docker Compose, Helm, local development, CI, and frontend build
  instructions are in [How to run](how-to-run.md).
