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

Management is a read-only operational dashboard: it provides direct inventory links and makes subnet
capacity easier to scan with available/monitor/action-needed labels derived from range utilization.

The shared desktop shell uses a grouped sidebar: Workspace contains the daily
inventory views, Catalog contains reusable IP data, and Operations contains
connectors, audit history, and import/export tools. It uses a light, cool-toned
surface aligned with the application canvas, remains fixed without its own scroll
bar, and keeps compact text-only account actions in the sidebar footer.

## Inventory and assignment

- IP assets store a unique address, type (`OS`, `BMC`, `VM`, `VIP`, `OTHER`),
  optional Project and Host, tags, notes, timestamps, and an archive flag.
- The IP Assets list is the primary project-assignment workflow. Use **Project
  Assignment → Unassigned only** or **Project → Unassigned** to find missing
  project assignments; there is no separate Needs Assignment page.
- Search, project/type/assignment filters, OR/AND/NOT tag filters, numeric IP
  sorting, pagination, bulk edits, and archived-only URLs are supported.
- Editors use right-side drawers for create/edit/archive/delete and bulk Project,
  Tag, Type, and Notes changes. The Host field provides a unified searchable
  combobox with real-time filtering, single-click selection, unassign support, and
  keyboard navigation. Destructive actions require acknowledgement and,
  for higher-risk records, exact-value confirmation.
- OS and BMC assets are paired through a shared Host. An unassigned BMC can
  create/reuse `server_<ip>` when `IPOCKET_AUTO_HOST_FOR_BMC` is enabled.
- The deterministic `ipocket_agent` package infers `/16`, `/24`, and scoped
  single-octet OS-to-BMC rules from confirmed Host relationships. It is a
  read-only analysis component: it receives an inventory snapshot and returns
  `CREATE_HOST`, `COMPLETE_HOST`, `UNMATCHED_ASSET`, or `CONFLICT` findings.
- Editors apply stable proposals through ipocket. Proposal fingerprints prevent
  stale writes, an idempotency key makes retries safe, and Host creation, asset
  links, the operator decision, and audit entries commit in one transaction.
  Manual investigation asks for the counterpart IP rather than a database ID:
  OS findings ask for BMC, and BMC findings ask for OS. ipocket creates the
  counterpart asset when needed and creates/reuses `server_<bmc-ip>`.

## Supporting catalogs

- Hosts group linked active IP assets into OS, BMC, and other addresses. Deleting
  a Host unlinks its IP assets rather than deleting them.
- Projects, Vendors, and Tags are managed from Library. Deleting a Project or
  Vendor clears the corresponding assignments; deleting a Tag removes its asset
  relationships.
- Library's Vendors tab (`/ui/projects?tab=vendors`) is the canonical Vendor UI.
  The legacy `/ui/vendors` URL redirects there for compatibility.
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
  Audit rows written during an import apply carry the username of the account that
  ran the import or connector.

## Operations

- `GET /health` returns application/build health metadata.
- `GET /metrics` exposes required IP inventory counters.
- `GET /sd/node` provides Prometheus HTTP service discovery.
- Authenticated users can read `GET /api/host-completion/summary`,
  `/findings`, and `/findings/next`. Editor-only
  `POST /api/host-completion/findings/decisions` applies operator outcomes.
- `/host-completion/analytics` shows the reconciliation states, the explicitly
  defined coverage formula, and rule support/contradictions. Superusers can
  add, edit, or deactivate explicit `/16` and `/24` IPv4 mappings there;
  deactivation preserves the rule and its audit history. Editors use
  `/host-completion/review` for the evidence-first one-at-a-time workflow.
- Docker, Docker Compose, Helm, local development, CI, and frontend build
  instructions are in [How to run](how-to-run.md).
