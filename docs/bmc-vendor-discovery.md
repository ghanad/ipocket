# BMC Vendor Auto-Discovery

## Overview
The BMC Vendor Auto-Discovery feature allows **ipocket** to automatically identify and assign hardware vendors (such as Dell, HPE, Supermicro, Cisco, Lenovo, Huawei, Inspur, Fujitsu, and Quanta) to servers by inspecting SSL/TLS certificates and banners on their linked Baseboard Management Controller (BMC) IP addresses on port 443.

This mechanism requires **zero credentials** on the BMCs, non-destructively probes target hosts concurrently using Python's asynchronous networking, and integrates with the database, CLI, and desktop React UI.

---

## How It Works

1. **Target Selection**:
   The engine queries for active (non-archived) IP assets of type `BMC` linked to hosts where `host.vendor_id` is currently unassigned (or specific hosts requested by the operator).

2. **Resilient Multi-Layer Probing**:
   - **Permissive SSL/TLS on Port 443**: Initiates a TLS handshake with certificate verification disabled (`CERT_NONE`) to support factory and self-signed certificates.
     - **DH Key Too Small (`dh_key_too_small`)**: Handled by setting OpenSSL `@SECLEVEL=0` and automatically retrying with DHE ciphers disabled (`DEFAULT:!DH:!DHE:@SECLEVEL=0`) if weak DH parameters are encountered, forcing the BMC to negotiate standard RSA/ECDHE.
     - **Handshake Failures (`sslv3_alert_handshake_failure`)**: Handled by allowing legacy TLS 1.0/1.1 protocols and adapting Server Name Indication (SNI) behaviour for older embedded BMC webservers.
     - Extracts human-readable strings from the ASN.1 DER certificate (Subject `CN`, `O`, Issuer, and `SAN`).
   - **HTTP Port 80 Banner Fallback**: If port 443 fails or times out, the scanner checks port 80 for HTTP `Server:` headers (e.g. `Server: HP-iLO-Server`), redirect `Location:` headers, and HTML `<title>` tags.
   - **UDP Port 623 IPMI RMCP Ping Fallback**: If web ports are unresponsive, a 12-byte ASF Presence Ping is sent to UDP port 623. The response ASF Pong yields the hardware manufacturer's IANA Enterprise ID (e.g. 674 for Dell, 232 for HPE, 10876 for Supermicro) with zero credentials.

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
