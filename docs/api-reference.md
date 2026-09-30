# API Reference & Documentation

ipocket exposes REST APIs, operational telemetry endpoints, and interactive API documentation.

## Interactive Documentation in the UI

You can view, search, and test all API endpoints directly in your browser:

- **Swagger UI (Interactive API Explorer):** [`/docs`](http://localhost:8000/docs)
  - Linked in the **Sidebar Navigation** under *Operations → API Docs*.
  - Linked in the **Sidebar Footer** next to *About ipocket*.
  - Linked in the **About** page ([`/ui/about`](http://localhost:8000/ui/about)) under *Operational links*.
- **ReDoc (API Reference):** [`/redoc`](http://localhost:8000/redoc)
- **OpenAPI JSON Schema:** [`/openapi.json`](http://localhost:8000/openapi.json)

> **Offline / Air-Gapped Production Support:**
> All JavaScript, CSS, and favicon assets for Swagger UI and ReDoc are self-hosted locally under `/static/vendor/`. No external CDN (e.g. `cdn.jsdelivr.net`) or external font requests (e.g. Google Fonts) are made, ensuring complete functionality in production networks without internet access.

---

## IP Assets Endpoints

### 1. List Active IP Assets
**`GET /ip-assets`**

Returns a flat list of active IP assets.

#### Query Parameters:
| Parameter | Type | Description |
|---|---|---|
| `type` | string | Filter by asset type: `OS`, `BMC`, `VM`, `VIP`, `OTHER` |
| `project_id` | integer | Filter by assigned project ID |
| `unassigned-only` | boolean | If `true`, returns only IP assets not assigned to any project |

#### Examples:
```bash
# Filter only BMC IP assets
curl -s "http://localhost:8000/ip-assets?type=BMC"

# Filter unassigned BMC IP assets
curl -s "http://localhost:8000/ip-assets?type=BMC&unassigned-only=true"

# Filter IP assets for project 2
curl -s "http://localhost:8000/ip-assets?project_id=2"
```

### 2. Get Single IP Asset
**`GET /ip-assets/{ip_address}`**

Returns details for a specific IP address including tags.

### 3. Advanced UI IP Assets Query
**`GET /api/ui/ip-assets`**

Used by the frontend with full pagination, search, and multi-tag filtering:
- `type`: `BMC`, `OS`, `VM`, `VIP`, `OTHER`
- `q`: Search query (IP address, hostname, notes, tags)
- `project_id`: Project ID or `unassigned`
- `tag`: Single tag filter
- `tag_all`: Match all specified tags (`tag_all=prod&tag_all=db`)
- `tag_any`: Match any specified tags
- `tag_not`: Exclude specified tags
- `assigned-only`: `true`/`false`
- `unassigned-only`: `true`/`false`
- `page`: Page number (1-based)
- `per-page`: 10, 20, 50, 100

---

## Hosts Endpoints

### 1. List Hosts
**`GET /hosts`**

Returns all managed host records (servers and machines):
```bash
curl -s "http://localhost:8000/hosts"
```

### 2. Get Host with Linked IPs
**`GET /hosts/{host_id}`**

Returns host details along with linked IP assets grouped by type (`os`, `bmc`, `other`):
```bash
curl -s "http://localhost:8000/hosts/1"
```

### 3. UI Hosts Query
**`GET /api/ui/hosts`**

Accepts `q`, `vendor_id`, `project_id`, `tag`, `status` (`linked` or `free`), and pagination (`page`, `per-page`).

---

## Export Endpoints

- `GET /export/ip-assets.csv`
- `GET /export/ip-assets.json`
- `GET /export/hosts.csv`
- `GET /export/hosts.json`
- `GET /export/bundle.json`
- `GET /export/bundle.zip`

---

## Operational & Telemetry Endpoints

- `GET /health`: Health check and build information.
- `GET /metrics`: Prometheus metrics scraper.
- `GET /sd/node`: Prometheus HTTP Service Discovery targets.
