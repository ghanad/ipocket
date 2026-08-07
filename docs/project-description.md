# Project description

ipocket is a lightweight, modular, desktop-focused web application for managing
an organization’s IP address inventory. It has a React/TypeScript user
interface, a FastAPI backend, and SQLite storage. Its goal is to keep network
addresses, the infrastructure they belong to, and their operational context in
one searchable and auditable internal system.

## Main entities

### IP Asset

An **IP Asset** is the central inventory record: one unique IP address that is
known to the organization. Each IP Asset contains:

- `ip_address`: the unique IP address.
- `ip_int`: a derived IPv4 integer used for numeric sorting and range queries.
- `type`: `OS`, `BMC`, `VM`, `VIP`, or `OTHER`.
- `project`: an optional Project assignment, used to show which project owns or
  uses the address.
- `host`: an optional link to a Host (the server or device the address belongs
  to).
- `tags`: zero or more labels for classification and filtering.
- `notes`: optional operational context or free-form documentation.
- `archived`: a soft-delete flag; archived records remain available for history
  and can be restored.
- `created_at` and `updated_at`: record timestamps.

The IP Assets list is the main working area. Operators can search and filter
records, review unassigned projects, make bulk changes, and create, edit,
archive, or restore assets through low-click drawer-based workflows.

### Host

A **Host** represents a physical server, virtual server, or other managed
device. It groups all IP Assets belonging to the same machine, rather than
duplicating server information in every IP record. A Host contains:

- `name`: a unique host or server name.
- `vendor`: an optional link to the hardware/device Vendor.
- `notes`: optional documentation about the host.

Hosts do not own separate IP-address or tag fields: their addresses and
visible tags are derived from linked active IP Assets. This supports common
relationships such as an operating-system (`OS`) IP and a management-controller
(`BMC`) IP belonging to the same server. Deleting a Host only removes this link;
the IP Asset records themselves are preserved.

### Other supporting entities

- **Project**: a named workstream or ownership grouping, with an optional
  description and display color.
- **Vendor**: a reusable vendor name that can be assigned to Hosts.
- **Tag**: a normalized, color-coded label; each IP Asset can have many Tags.
- **IP Range**: a named IPv4 CIDR range used to calculate used/free capacity
  from the current IP Asset inventory.
- **User and Session**: authenticated access with Viewer, Editor, and Admin
  roles.
- **Audit Log**: immutable history of important changes to IP Assets, users,
  imports, and connector apply operations.

## Workflows and integrations

ipocket supports searchable lists, URL-backed filters and pagination,
project-assignment review, bulk edits, archived-record history, CSV/JSON/bundle
exports, and bundle/CSV/Nmap XML imports. Connector-driven ingestion can bring
inventory data from systems such as vCenter, Prometheus, Elasticsearch,
Cassandra, Ceph, and Kubernetes while applying the same validation and audit
rules as manual changes.

For operations, the application exposes Prometheus-compatible inventory metrics
at `GET /metrics` and HTTP service discovery at `GET /sd/node`. The project is
intended to remain simple and extensible: validation, authorization, audit
logging, automated tests, and concise documentation protect changes as the
inventory model evolves.
