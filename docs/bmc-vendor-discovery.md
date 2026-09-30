# BMC Vendor Auto-Discovery

## Overview
The BMC Vendor Auto-Discovery feature allows **ipocket** to automatically identify and assign hardware vendors (such as Dell, HPE, Supermicro, Cisco, Lenovo, Huawei, Inspur, Fujitsu, and Quanta) to servers by inspecting SSL/TLS certificates and banners on their linked Baseboard Management Controller (BMC) IP addresses on port 443.

This mechanism requires **zero credentials** on the BMCs, non-destructively probes target hosts concurrently using Python's asynchronous networking, and integrates with the database, CLI, and desktop React UI.

---

## How It Works

1. **Target Selection**:
   The engine queries for active (non-archived) IP assets of type `BMC` linked to hosts where `host.vendor_id` is currently unassigned (or specific hosts requested by the operator).

2. **Zero-Credentials SSL/TLS Probing**:
   The scanner connects to port 443 of each BMC IP and initiates a TLS handshake with certificate verification disabled (`CERT_NONE`) to support factory and self-signed certificates.
   It extracts human-readable strings from the ASN.1 DER certificate, including:
   - Subject Common Name (`CN`) and Organization (`O`)
   - Issuer Common Name and Organization
   - Subject Alternative Names (`SAN`)

3. **Vendor Normalization**:
   The extracted text is matched against signature rules to resolve standard vendor names:
   - **Dell**: `dell`, `idrac`, `poweredge`
   - **HPE**: `hewlett-packard`, `hpe`, `ilo`, `proliant`
   - **Supermicro**: `super micro`, `supermicro`, `megarac`, `american megatrends`
   - **Cisco**: `cisco`, `cimc`, `ucs`
   - **Lenovo**: `lenovo`, `xclarity`, `imm2`, `thinksystem`, `thinkserver`
   - **Huawei**: `huawei`, `ibmc`
   - **Inspur**: `inspur`
   - **Fujitsu**: `fujitsu`, `primergy`, `irmc`
   - **Quanta**: `quanta`, `qct`

4. **Persistence & Auditing**:
   When applying results:
   - If a detected vendor is not yet present in the `vendors` catalog, it is automatically created.
   - The host's `vendor_id` is updated.
   - An entry is recorded in `AuditLog` (`action="UPDATE"`, `target_type="HOST"`).

---

## Web UI Usage

In the **Hosts** list page (`/ui/hosts`), editors will see a **Discover Vendors (BMC)** button in the header actions:
1. Clicking the button opens the right-hand discovery drawer.
2. The drawer shows the count of eligible hosts with BMC IPs currently lacking a vendor.
3. Configure socket timeout (default: 2s) and click **Run Discovery Scan**.
4. Results are displayed in an interactive table showing:
   - Checkbox to select/deselect
   - Host Name & BMC IP
   - Discovery Status badge (`matched`, `unmatched`, `timeout`)
   - Suggested Vendor (with dropdown to override if necessary)
   - Evidence snippet extracted from the certificate
5. Review the suggestions and click **Apply to Selected** to commit changes to the inventory.

---

## CLI Usage

Run discovery directly from the terminal or in automated cron pipelines:

```bash
# Dry run scan displaying tabular results to stdout (no database changes)
python -m app.cli.bmc_discovery --dry-run

# Output results as structured JSON
python -m app.cli.bmc_discovery --dry-run --json

# Scan specific hosts by ID
python -m app.cli.bmc_discovery --host-id 12 --host-id 15

# Automatically scan and apply high-confidence matches
python -m app.cli.bmc_discovery --apply

# Custom timeout and concurrency settings
python -m app.cli.bmc_discovery --timeout 3.0 --concurrency 30 --apply
```

---

## API Endpoints

All endpoints require authentication (Bearer token or authenticated UI session):

- `GET /api/hosts/bmc-discovery/targets`:
  Returns hosts eligible for BMC discovery with linked BMC assets.
  - Query parameters: `host_id` (repeatable), `all_hosts` (boolean).

- `POST /api/hosts/bmc-discovery/scan`:
  Triggers concurrent TLS probing on targets.
  - Request body (optional):
    ```json
    {
      "host_ids": [1, 2],
      "timeout": 2.0,
      "concurrency": 20
    }
    ```

- `POST /api/hosts/bmc-discovery/apply`:
  Applies selected vendors to hosts. Requires Editor or Admin role.
  - Request body:
    ```json
    {
      "items": [
        { "host_id": 1, "vendor_name": "Dell" },
        { "host_id": 2, "vendor_name": "HPE" }
      ]
    }
    ```
