import { useEffect, useRef, useState } from "react";

import {
  applyBMCVendors,
  fetchBMCTargets,
  scanBMCVendors,
  type BMCTarget,
  type BMCScanResult,
} from "./bmcDiscoveryApi";
import type { FilterOption } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
  vendors: FilterOption[];
}

interface ScanRow extends BMCScanResult {
  selected: boolean;
  chosenVendor: string;
}

export function BMCDiscoveryDrawer({
  open,
  onClose,
  onApplied,
  vendors,
}: Props) {
  const ref = useRef<HTMLElement>(null);
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [targets, setTargets] = useState<BMCTarget[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanRows, setScanRows] = useState<ScanRow[] | null>(null);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [timeoutSec, setTimeoutSec] = useState(2.0);

  useEffect(() => {
    if (!open) {
      setScanRows(null);
      setError(null);
      setSuccessMessage(null);
      return;
    }

    setLoadingTargets(true);
    fetchBMCTargets()
      .then((res) => {
        setTargets(res.targets);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load targets");
      })
      .finally(() => {
        setLoadingTargets(false);
      });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open, onClose]);

  const handleStartScan = async () => {
    setScanning(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await scanBMCVendors({ timeout: timeoutSec });
      const rows: ScanRow[] = res.results.map((r) => ({
        ...r,
        selected: r.status === "matched" && Boolean(r.detected_vendor),
        chosenVendor: r.detected_vendor ?? "",
      }));
      setScanRows(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const handleApply = async () => {
    if (!scanRows) return;
    const toApply = scanRows
      .filter((r) => r.selected && r.chosenVendor.trim())
      .map((r) => ({
        host_id: r.host_id,
        vendor_name: r.chosenVendor.trim(),
      }));

    if (toApply.length === 0) return;

    setApplying(true);
    setError(null);
    try {
      const res = await applyBMCVendors(toApply);
      setSuccessMessage(`Successfully applied vendor to ${res.count} host(s).`);
      // Update targets and local rows
      const appliedIds = new Set(toApply.map((item) => item.host_id));
      setTargets((prev) => prev.filter((t) => !appliedIds.has(t.host_id)));
      setScanRows((prev) =>
        prev
          ? prev.filter((r) => !appliedIds.has(r.host_id))
          : null,
      );
      onApplied();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply vendors");
    } finally {
      setApplying(false);
    }
  };

  const matchedCount = scanRows
    ? scanRows.filter((r) => r.status === "matched").length
    : 0;
  const selectedCount = scanRows
    ? scanRows.filter((r) => r.selected && r.chosenVendor.trim()).length
    : 0;

  const toggleSelectAll = (checked: boolean) => {
    if (!scanRows) return;
    setScanRows(
      scanRows.map((r) => ({
        ...r,
        selected: checked && Boolean(r.chosenVendor.trim()),
      })),
    );
  };

  const updateRow = (index: number, patch: Partial<ScanRow>) => {
    if (!scanRows) return;
    const next = [...scanRows];
    next[index] = { ...next[index], ...patch };
    setScanRows(next);
  };

  return (
    <>
      <div
        className={`host-drawer-overlay${open ? " is-open" : ""}`}
        aria-hidden="true"
        onClick={onClose}
      />
      <aside
        ref={ref}
        className={`host-drawer bmc-discovery-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Discover Vendors via BMC"
      >
        <header className="host-drawer-header">
          <div className="host-drawer-header-row">
            <div>
              <p className="eyebrow">Hardware Discovery</p>
              <h2 className="host-drawer-title">Discover Vendors via BMC (SSL)</h2>
              <p className="subtitle">
                Probes BMC IP addresses on port 443 over SSL/TLS to identify server hardware vendors.
              </p>
            </div>
            <button
              className="btn btn-ghost host-drawer-close"
              type="button"
              aria-label="Close discovery drawer"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </header>

        <div className="host-drawer-body">
          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}
          {successMessage && (
            <div className="alert alert-success" role="status">
              {successMessage}
            </div>
          )}

          <section className="card compact-card bmc-discovery-controls">
            <div className="bmc-discovery-summary-row">
              <div>
                <strong>Eligible Hosts:</strong>{" "}
                {loadingTargets ? (
                  <span>Checking…</span>
                ) : (
                  <span>
                    {targets.length} host(s) without vendor have linked BMC IPs
                  </span>
                )}
              </div>
              <div className="bmc-discovery-actions">
                <label className="field-inline" style={{ fontSize: "13px" }}>
                  <span>Timeout:</span>
                  <select
                    className="select select-minimal"
                    value={timeoutSec}
                    disabled={scanning}
                    onChange={(e) => setTimeoutSec(Number(e.target.value))}
                  >
                    <option value={1.0}>1s</option>
                    <option value={2.0}>2s</option>
                    <option value={4.0}>4s</option>
                  </select>
                </label>
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={scanning || loadingTargets || targets.length === 0}
                  onClick={handleStartScan}
                >
                  {scanning ? "Scanning BMCs…" : "Run Discovery Scan"}
                </button>
              </div>
            </div>
          </section>

          {scanRows !== null && (
            <section className="bmc-discovery-results">
              <div className="bmc-discovery-results-header">
                <h3>Scan Results</h3>
                <span className="table-meta">
                  {matchedCount} of {scanRows.length} hosts matched
                </span>
              </div>

              {scanRows.length === 0 ? (
                <div className="empty-state">No hosts scanned.</div>
              ) : (
                <div className="table-responsive">
                  <table className="table bmc-results-table">
                    <thead>
                      <tr>
                        <th style={{ width: "40px" }}>
                          <input
                            type="checkbox"
                            aria-label="Select all matched"
                            checked={
                              scanRows.length > 0 &&
                              scanRows
                                .filter((r) => Boolean(r.chosenVendor.trim()))
                                .every((r) => r.selected)
                            }
                            onChange={(e) => toggleSelectAll(e.target.checked)}
                          />
                        </th>
                        <th>Host</th>
                        <th>BMC IP</th>
                        <th>Status</th>
                        <th>Vendor</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scanRows.map((row, idx) => (
                        <tr key={row.host_id} className={`status-row-${row.status}`}>
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`Select ${row.host_name}`}
                              checked={row.selected}
                              disabled={!row.chosenVendor.trim()}
                              onChange={(e) =>
                                updateRow(idx, { selected: e.target.checked })
                              }
                            />
                          </td>
                          <td>
                            <strong>{row.host_name}</strong>
                          </td>
                          <td>
                            <code>{row.bmc_ip ?? "—"}</code>
                          </td>
                          <td>
                            <span
                              className={`badge badge-${
                                row.status === "matched"
                                  ? "success"
                                  : row.status === "timeout"
                                    ? "warning"
                                    : "muted"
                              }`}
                            >
                              {row.status}
                            </span>
                          </td>
                          <td>
                            <input
                              type="text"
                              className="input input-compact"
                              list="bmc-known-vendors"
                              value={row.chosenVendor}
                              placeholder="Vendor"
                              onChange={(e) =>
                                updateRow(idx, {
                                  chosenVendor: e.target.value,
                                  selected: Boolean(e.target.value.trim()),
                                })
                              }
                            />
                          </td>
                          <td>
                            <span
                              className="bmc-evidence-cell"
                              title={row.fingerprint_summary ?? ""}
                            >
                              {row.fingerprint_summary ?? "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <datalist id="bmc-known-vendors">
                    {vendors.map((v) => (
                      <option key={v.id} value={v.name} />
                    ))}
                    <option value="Dell" />
                    <option value="HPE" />
                    <option value="Supermicro" />
                    <option value="Cisco" />
                    <option value="Lenovo" />
                    <option value="Huawei" />
                    <option value="Inspur" />
                  </datalist>
                </div>
              )}
            </section>
          )}
        </div>

        <footer className="host-drawer-footer">
          <span className="host-drawer-footer-status">
            {selectedCount > 0 ? `${selectedCount} host(s) selected` : ""}
          </span>
          <div className="host-drawer-footer-actions">
            <button
              className="btn btn-secondary"
              type="button"
              onClick={onClose}
              disabled={applying || scanning}
            >
              Close
            </button>
            <button
              className="btn btn-primary"
              type="button"
              disabled={selectedCount === 0 || applying || scanning}
              onClick={handleApply}
            >
              {applying ? "Applying…" : `Apply to Selected (${selectedCount})`}
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}
