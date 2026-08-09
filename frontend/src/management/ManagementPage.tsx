import { useCallback, useEffect, useState } from "react";

import { fetchManagementOverview } from "./api";
import type { ManagementOverview, ManagementSummary, RangeUtilization } from "./types";

interface ManagementPageProps {
  endpoint: string;
}

const inventoryMetrics: Array<{
  key: Exclude<keyof ManagementSummary, "active_ip_total">;
  label: string;
  helper: string;
  href: string;
}> = [
  { key: "archived_ip_total", label: "Archived IPs", helper: "Soft-deleted records", href: "/ui/ip-assets?archived-only=true" },
  { key: "host_total", label: "Hosts", helper: "Hardware or VM entries", href: "/ui/hosts" },
  { key: "vendor_total", label: "Vendors", helper: "Manufacturer catalog", href: "/ui/projects?tab=vendors" },
  { key: "project_total", label: "Projects", helper: "Active assignments", href: "/ui/projects" },
];

function getCapacityStatus(utilizationPercent: number) {
  if (utilizationPercent >= 90) return { label: "Action needed", tone: "critical" };
  if (utilizationPercent >= 70) return { label: "Monitor", tone: "watch" };
  return { label: "Available", tone: "available" };
}

function utilizationWidth(utilizationPercent: number) {
  return Math.min(100, Math.max(0, utilizationPercent));
}

export function ManagementPage({ endpoint }: ManagementPageProps) {
  const [overview, setOverview] = useState<ManagementOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOverview(await fetchManagementOverview(endpoint));
    } catch {
      setError("Management data could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  if (loading) {
    return <><PageHeader subtitle="Loading inventory health and capacity…" /><section className="management-loading" aria-busy="true"><p role="status">Loading management data…</p></section></>;
  }

  if (error || !overview) {
    return <><PageHeader subtitle="A focused view of inventory health and capacity." /><section className="management-error" aria-labelledby="management-error-title"><div><p className="management-section-kicker">Connection issue</p><h2 id="management-error-title">Dashboard is unavailable</h2><p className="subtitle" role="alert">{error}</p></div><button className="btn btn-primary" type="button" onClick={loadOverview}>Try again</button></section></>;
  }

  return (
    <>
      <PageHeader subtitle="A focused view of inventory health and capacity." onRefresh={loadOverview} />
      <section className="management-inventory" aria-labelledby="inventory-summary-title">
        <div className="management-inventory-primary">
          <p className="management-section-kicker">Inventory footprint</p>
          <h2 id="inventory-summary-title">{overview.summary.active_ip_total.toLocaleString()} active IPs</h2>
          <p>Addresses currently in service across the inventory.</p>
          <a className="management-inline-link" href="/ui/ip-assets">Review IP assets <span aria-hidden="true">→</span></a>
        </div>
        <div className="management-metric-list" aria-label="Inventory totals">
          {inventoryMetrics.map((metric) => <a className="management-metric" href={metric.href} aria-label={`View ${metric.label.toLowerCase()}`} key={metric.key}><span className="management-metric-label">{metric.label}</span><strong>{overview.summary[metric.key].toLocaleString()}</strong><span className="management-metric-helper">{metric.helper}</span></a>)}
        </div>
      </section>
      <section className="management-capacity" aria-labelledby="capacity-title">
        <div className="management-capacity-header"><div><p className="management-section-kicker">Capacity</p><h2 id="capacity-title">Subnet utilization</h2><p className="subtitle">Find ranges that need capacity attention, then open their address lists.</p></div><a className="btn btn-secondary" href="/ui/ranges">Manage ranges</a></div>
        <div className="table-wrapper"><table className="table management-utilization-table"><thead><tr><th>Name</th><th>CIDR</th><th>Total usable</th><th>Used</th><th>Free</th><th>Utilization</th></tr></thead><tbody>{overview.utilization.length === 0 ? <tr><td colSpan={6} className="empty-state">No ranges yet. Add ranges to see utilization.</td></tr> : overview.utilization.map((row) => <UtilizationRow key={row.id} row={row} />)}</tbody></table></div>
      </section>
    </>
  );
}

function UtilizationRow({ row }: { row: RangeUtilization }) {
  const status = getCapacityStatus(row.utilization_percent);
  return <tr><td><a className="management-range-link" href={`/ui/ranges/${row.id}/addresses`}>{row.name}</a></td><td><span className="management-cidr">{row.cidr}</span></td><td>{row.total_usable.toLocaleString()}</td><td><a className="link" href={`/ui/ranges/${row.id}/addresses#used`}>{row.used.toLocaleString()}</a></td><td><a className="link" href={`/ui/ranges/${row.id}/addresses#free`}>{row.free.toLocaleString()}</a></td><td><div className="management-capacity-meter"><div className="management-capacity-meter-copy"><span>{row.utilization_percent.toFixed(1)}%</span><span className={`management-capacity-status is-${status.tone}`}>{status.label}</span></div><div className="management-capacity-track" aria-hidden="true"><span className={`management-capacity-fill is-${status.tone}`} style={{ width: `${utilizationWidth(row.utilization_percent)}%` }} /></div><span className="visually-hidden">{status.label}: {row.utilization_percent.toFixed(1)}% utilized</span></div></td></tr>;
}

function PageHeader({ subtitle, onRefresh }: { subtitle: string; onRefresh?: () => void }) {
  return <section className="page-header"><div><p className="management-section-kicker">Management</p><h1>Management Overview</h1><p className="subtitle">{subtitle}</p></div>{onRefresh ? <button className="btn btn-secondary" type="button" onClick={onRefresh}>Refresh data</button> : null}</section>;
}
