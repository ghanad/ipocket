import { useCallback, useEffect, useState } from "react";

import { fetchManagementOverview } from "./api";
import type { ManagementOverview, ManagementSummary } from "./types";

interface ManagementPageProps {
  endpoint: string;
}

const summaryCards: Array<{
  key: keyof ManagementSummary;
  label: string;
  helper: string;
  href: string;
}> = [
  {
    key: "active_ip_total",
    label: "Active IPs",
    helper: "IPs currently in service",
    href: "/ui/ip-assets",
  },
  {
    key: "archived_ip_total",
    label: "Archived IPs",
    helper: "Soft-deleted records",
    href: "/ui/ip-assets?archived-only=true",
  },
  {
    key: "host_total",
    label: "Hosts",
    helper: "Distinct hardware or VM entries",
    href: "/ui/hosts",
  },
  {
    key: "vendor_total",
    label: "Vendors",
    helper: "Partner or manufacturer list",
    href: "/ui/vendors",
  },
  {
    key: "project_total",
    label: "Projects",
    helper: "Active assignments",
    href: "/ui/projects",
  },
];

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
    return (
      <>
        <PageHeader subtitle="Loading inventory health and coverage…" />
        <section className="card">
          <div className="card-header card-header-padded">
            <p role="status">Loading management data…</p>
          </div>
        </section>
      </>
    );
  }

  if (error || !overview) {
    return (
      <>
        <PageHeader subtitle="Quick snapshot of inventory health and coverage." />
        <section className="card">
          <div className="card-header card-header-padded">
            <div>
              <h2>Unable to load dashboard</h2>
              <p className="subtitle" role="alert">
                {error}
              </p>
            </div>
            <button className="btn btn-primary" type="button" onClick={loadOverview}>
              Try again
            </button>
          </div>
        </section>
      </>
    );
  }

  return (
    <>
      <PageHeader subtitle="Quick snapshot of inventory health and coverage." />

      <section className="stats-grid">
        {summaryCards.map((card) => (
          <a
            className="card stat-card stat-card-link"
            href={card.href}
            aria-label={`View ${card.label.toLowerCase()}`}
            key={card.key}
          >
            <p className="stat-label">{card.label}</p>
            <p className="stat-value">{overview.summary[card.key]}</p>
            <p className="stat-helper">{card.helper}</p>
          </a>
        ))}
      </section>

      <section className="card table-card">
        <div className="card-header card-header-padded">
          <div>
            <h2>Subnet Utilization</h2>
            <p className="subtitle">Track used vs. free IPs in each defined range.</p>
          </div>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>CIDR</th>
                <th>Total usable</th>
                <th>Used</th>
                <th>Free</th>
                <th>Utilization</th>
              </tr>
            </thead>
            <tbody>
              {overview.utilization.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-state">
                    No ranges yet. Add ranges to see utilization.
                  </td>
                </tr>
              ) : (
                overview.utilization.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.cidr}</td>
                    <td>{row.total_usable}</td>
                    <td>
                      <a className="link" href={`/ui/ranges/${row.id}/addresses#used`}>
                        {row.used}
                      </a>
                    </td>
                    <td>
                      <a className="link" href={`/ui/ranges/${row.id}/addresses#free`}>
                        {row.free}
                      </a>
                    </td>
                    <td>{row.utilization_percent.toFixed(1)}%</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function PageHeader({ subtitle }: { subtitle: string }) {
  return (
    <section className="page-header">
      <div>
        <h1>Management Overview</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
    </section>
  );
}
