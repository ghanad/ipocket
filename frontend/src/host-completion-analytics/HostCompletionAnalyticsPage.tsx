/*
THESIS: Host completeness is a relationship diagnostic, not a pile of KPIs.
OWN-WORLD: Inherit ipocket's white operational surfaces, blue primary signal,
and compact data rows; reserve green, amber, and violet for chart meaning.
STORY: See overall completion, isolate the missing side, then judge discovered
address mappings by evidence and coverage.
FIRST VIEWPORT: Header leads into one wide stacked completion
bar, followed by incomplete and IP-type distributions.
FORM: A scan-first operations dashboard using incumbent cards and table rhythm;
the precisely specified route does not require concept staging or a seed.
*/
import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchHostCompletionAnalytics } from "./api";
import type {
  HostCompletionAnalytics,
  HostCompletionIPTypeCounts,
  HostCompletionPattern,
} from "./types";

interface HostCompletionAnalyticsPageProps {
  endpoint: string;
}

const numberFormatter = new Intl.NumberFormat();

const breakdownItems = [
  { key: "os_only", label: "OS only", color: "var(--hc-os)" },
  { key: "bmc_only", label: "BMC only", color: "var(--hc-bmc)" },
  { key: "unlinked", label: "Unlinked", color: "var(--hc-unlinked)" },
] as const;

const ipTypeItems: Array<{
  key: keyof HostCompletionIPTypeCounts;
  label: string;
}> = [
  { key: "OS", label: "OS" },
  { key: "BMC", label: "BMC" },
  { key: "VM", label: "VM" },
  { key: "unknown", label: "Unknown" },
];

function percentage(value: number, total: number): number {
  return total > 0 ? (value / total) * 100 : 0;
}

function widthStyle(value: number): CSSProperties {
  return { "--bar-width": `${Math.max(0, Math.min(value, 100))}%` } as CSSProperties;
}

export function HostCompletionAnalyticsPage({
  endpoint,
}: HostCompletionAnalyticsPageProps) {
  const [analytics, setAnalytics] = useState<HostCompletionAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAnalytics = useCallback(
    async () => {
      setLoading(true);
      setError(null);
      try {
        setAnalytics(await fetchHostCompletionAnalytics(endpoint));
      } catch {
        setError("Host Completion analytics could not be loaded. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [endpoint],
  );

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  if (loading && !analytics) {
    return <AnalyticsLoadingState />;
  }

  if (!analytics) {
    return (
      <>
        <PageHeader />
        <section className="card hc-error-state">
          <div>
            <h2>Unable to load analytics</h2>
            <p className="subtitle" role="alert">
              {error}
            </p>
          </div>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => void loadAnalytics()}
          >
            Try again
          </button>
        </section>
      </>
    );
  }

  return (
    <>
      <PageHeader />
      {error ? (
        <p className="hc-refresh-warning" role="alert">
          Reload failed. Displaying the most recently loaded analytics.
        </p>
      ) : null}

      <CompletionOverview analytics={analytics} />

      <section className="hc-distribution-grid" aria-label="Host and IP distributions">
        <IncompleteBreakdown analytics={analytics} />
        <IPTypeDistribution counts={analytics.ip_type_counts} />
      </section>

      <PatternList
        patterns={analytics.patterns}
        confirmedPairs={analytics.confirmed_pairs}
      />
    </>
  );
}

function PageHeader() {
  return (
    <section className="page-header">
      <div>
        <p className="eyebrow">Inventory relationships</p>
        <h1>Host Completion Analytics</h1>
        <p className="subtitle">
          Measure OS/BMC coverage and evaluate recurring address mappings.
        </p>
      </div>
      <div className="hc-header-actions">
        <a className="btn btn-primary" href="/host-completion/review">
          Review hosts
        </a>
      </div>
    </section>
  );
}

function CompletionOverview({ analytics }: { analytics: HostCompletionAnalytics }) {
  const completePercent = percentage(analytics.complete_hosts, analytics.total_hosts);
  const incompletePercent = percentage(
    analytics.incomplete_hosts,
    analytics.total_hosts,
  );

  return (
    <section className="card hc-completion-card" aria-labelledby="completion-heading">
      <div className="card-header">
        <div>
          <h2 id="completion-heading">Host completion</h2>
          <p className="subtitle">
            {numberFormatter.format(analytics.total_hosts)} total hosts in inventory
          </p>
        </div>
        <p className="hc-completion-rate">
          <strong>{completePercent.toFixed(1)}%</strong>
          <span>complete</span>
        </p>
      </div>

      <div
        className="hc-stacked-bar"
        role="img"
        aria-label={`${analytics.complete_hosts} complete hosts and ${analytics.incomplete_hosts} incomplete hosts`}
      >
        <span
          className="hc-stacked-bar-complete"
          style={{ width: `${completePercent}%` }}
        />
        <span
          className="hc-stacked-bar-incomplete"
          style={{ width: `${incompletePercent}%` }}
        />
      </div>

      <div className="hc-completion-legend">
        <ChartLegendItem
          label="Complete"
          value={analytics.complete_hosts}
          helper="Active OS and BMC"
          color="var(--hc-complete)"
        />
        <ChartLegendItem
          label="Incomplete"
          value={analytics.incomplete_hosts}
          helper="One or both sides missing"
          color="var(--hc-incomplete)"
        />
        <ChartLegendItem
          label="Confirmed pairs"
          value={analytics.confirmed_pairs}
          helper="OS × BMC combinations"
          color="var(--color-primary)"
        />
      </div>
    </section>
  );
}

function ChartLegendItem({
  label,
  value,
  helper,
  color,
}: {
  label: string;
  value: number;
  helper: string;
  color: string;
}) {
  return (
    <div className="hc-legend-item">
      <span className="hc-legend-swatch" style={{ background: color }} aria-hidden="true" />
      <div>
        <p className="hc-legend-label">{label}</p>
        <p className="hc-legend-value">{numberFormatter.format(value)}</p>
        <p className="hc-legend-helper">{helper}</p>
      </div>
    </div>
  );
}

function IncompleteBreakdown({ analytics }: { analytics: HostCompletionAnalytics }) {
  const total = Object.values(analytics.breakdown).reduce(
    (sum, value) => sum + value,
    0,
  );
  const osEnd = percentage(analytics.breakdown.os_only, total);
  const bmcEnd = osEnd + percentage(analytics.breakdown.bmc_only, total);
  const pieBackground =
    total > 0
      ? `conic-gradient(var(--hc-os) 0 ${osEnd}%, var(--hc-bmc) ${osEnd}% ${bmcEnd}%, var(--hc-unlinked) ${bmcEnd}% 100%)`
      : "var(--color-border)";

  return (
    <section className="card hc-breakdown-card" aria-labelledby="breakdown-heading">
      <div className="card-header">
        <div>
          <h2 id="breakdown-heading">Incomplete hosts</h2>
          <p className="subtitle">Which relationship is missing</p>
        </div>
      </div>
      <div className="hc-pie-layout">
        <div
          className="hc-pie"
          style={{ background: pieBackground }}
          role="img"
          aria-label={`OS only ${analytics.breakdown.os_only}, BMC only ${analytics.breakdown.bmc_only}, unlinked ${analytics.breakdown.unlinked}`}
        >
          <div className="hc-pie-center">
            <strong>{numberFormatter.format(total)}</strong>
            <span>incomplete</span>
          </div>
        </div>
        <ul className="hc-pie-legend">
          {breakdownItems.map((item) => (
            <li key={item.key}>
              <span
                className="hc-legend-swatch"
                style={{ background: item.color }}
                aria-hidden="true"
              />
              <span>{item.label}</span>
              <strong>{numberFormatter.format(analytics.breakdown[item.key])}</strong>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function IPTypeDistribution({ counts }: { counts: HostCompletionIPTypeCounts }) {
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0);

  return (
    <section className="card hc-ip-types-card" aria-labelledby="ip-types-heading">
      <div className="card-header">
        <div>
          <h2 id="ip-types-heading">IP type distribution</h2>
          <p className="subtitle">
            {numberFormatter.format(total)} active addresses
          </p>
        </div>
      </div>
      <div className="hc-type-list">
        {ipTypeItems.map((item) => {
          const value = counts[item.key];
          const share = percentage(value, total);
          return (
            <div className="hc-type-row" key={item.key}>
              <div className="hc-type-meta">
                <span>{item.label}</span>
                <span>
                  <strong>{numberFormatter.format(value)}</strong>
                  {" · "}
                  {share.toFixed(1)}%
                </span>
              </div>
              <div
                className={`hc-meter hc-meter-${item.key.toLowerCase()}`}
                role="progressbar"
                aria-label={`${item.label} addresses`}
                aria-valuemin={0}
                aria-valuemax={total}
                aria-valuenow={value}
              >
                <span style={widthStyle(share)} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PatternList({
  patterns,
  confirmedPairs,
}: {
  patterns: HostCompletionPattern[];
  confirmedPairs: number;
}) {
  return (
    <section className="card hc-patterns-card" aria-labelledby="patterns-heading">
      <div className="card-header">
        <div>
          <h2 id="patterns-heading">Discovered address patterns</h2>
          <p className="subtitle">
            Prefix replacements supported by confirmed OS/BMC pairs
          </p>
        </div>
        <span className="hc-pattern-count">
          {numberFormatter.format(patterns.length)} {patterns.length === 1 ? "pattern" : "patterns"}
        </span>
      </div>

      {patterns.length === 0 ? (
        <div className="empty-state hc-pattern-empty">
          No supported /16 replacement patterns have been discovered yet.
        </div>
      ) : (
        <div className="hc-pattern-list">
          {patterns.map((pattern) => (
            <article
              className="hc-pattern-row"
              key={`${pattern.source_prefix}-${pattern.target_prefix}`}
            >
              <div className="hc-pattern-route">
                <code>{pattern.source_prefix}</code>
                <span aria-hidden="true">→</span>
                <code>{pattern.target_prefix}</code>
              </div>
              <div className="hc-pattern-evidence">
                <span>
                  <strong>{numberFormatter.format(pattern.support)}</strong> support
                </span>
                <span>
                  <strong>{numberFormatter.format(pattern.contradictions)}</strong>{" "}
                  contradictions
                </span>
              </div>
              <div className="hc-confidence">
                <div className="hc-confidence-label">
                  <span>Coverage confidence</span>
                  <strong>{pattern.coverage_percent.toFixed(1)}%</strong>
                </div>
                <div
                  className="hc-meter hc-meter-confidence"
                  role="progressbar"
                  aria-label={`${pattern.source_prefix} to ${pattern.target_prefix} confidence`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pattern.coverage_percent}
                >
                  <span style={widthStyle(pattern.coverage_percent)} />
                </div>
                <span className="visually-hidden">
                  {pattern.support} of {confirmedPairs} confirmed pairs covered
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function AnalyticsLoadingState() {
  return (
    <>
      <PageHeader />
      <section className="card hc-loading" aria-busy="true">
        <p role="status">Loading Host Completion analytics…</p>
        <div className="hc-skeleton hc-skeleton-heading" />
        <div className="hc-skeleton hc-skeleton-chart" />
        <div className="hc-skeleton hc-skeleton-row" />
        <div className="hc-skeleton hc-skeleton-row hc-skeleton-row-short" />
      </section>
    </>
  );
}
