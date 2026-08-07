import { useCallback, useEffect, useState } from "react";

import { fetchHostCompletionAnalytics } from "./api";
import type { HostCompletionAnalytics, ReconciliationRule } from "./types";

interface Props { endpoint: string; }

const number = new Intl.NumberFormat();

export function HostCompletionAnalyticsPage({ endpoint }: Props) {
  const [analytics, setAnalytics] = useState<HostCompletionAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setAnalytics(await fetchHostCompletionAnalytics(endpoint)); }
    catch { setError("The reconciliation summary could not be loaded. Please try again."); }
    finally { setLoading(false); }
  }, [endpoint]);

  useEffect(() => { void load(); }, [load]);
  if (loading && !analytics) return <><Header /><Loading /></>;
  if (!analytics) return <><Header /><section className="card hc-error-state"><div><h2>Unable to load summary</h2><p className="subtitle" role="alert">{error}</p></div><button className="btn btn-primary" type="button" onClick={() => void load()}>Try again</button></section></>;

  return (
    <>
      <Header />
      {error ? <p className="hc-refresh-warning" role="alert">Reload failed. Displaying the most recent summary.</p> : null}
      <section className="hc-kpi-grid" aria-label="Reconciliation KPIs">
        <Kpi label="Unexplained" value={analytics.unexplained_active_assets} helper="Goal: zero active OS/BMC assets" tone={analytics.unexplained_active_assets ? "warning" : "good"} />
        <Kpi label="Coverage" value={`${analytics.reconciliation_coverage.toFixed(1)}%`} helper="Resolved + proposed + exceptions" tone="primary" />
        <Kpi label="Host creations" value={analytics.proposed_host_creations} helper="Safe CREATE_HOST proposals" />
        <Kpi label="Conflicts" value={analytics.conflicts} helper="Requires explicit operator review" tone={analytics.conflicts ? "danger" : "good"} />
      </section>
      <section className="card hc-state-card" aria-labelledby="states-heading">
        <div className="card-header"><div><h2 id="states-heading">Asset reconciliation states</h2><p className="subtitle">Every active OS/BMC asset has one operational state</p></div><span className="hc-total">{number.format(analytics.active_assets)} active assets</span></div>
        <div className="hc-state-grid">
          {Object.entries(analytics.states).map(([state, value]) => <div className={`hc-state hc-state-${state.toLowerCase()}`} key={state}><span>{state.toLowerCase()}</span><strong>{number.format(value)}</strong></div>)}
        </div>
        <div className="hc-attached-row"><span>OS attached <strong>{analytics.os_attached_to_hosts} / {analytics.active_os_assets}</strong></span><span>BMC attached <strong>{analytics.bmc_attached_to_hosts} / {analytics.active_bmc_assets}</strong></span><span>Explicit exceptions <strong>{analytics.explicit_exceptions}</strong></span><span>Incomplete Hosts <strong>{analytics.incomplete_hosts}</strong></span></div>
      </section>
      <Rules rules={analytics.rules} />
    </>
  );
}

function Header() {
  return <section className="page-header"><div><p className="eyebrow">Inventory reconciliation</p><h1>Host Completion</h1><p className="subtitle">Measure explainable OS/BMC reconciliation without forced matches.</p></div><a className="btn btn-primary" href="/host-completion/review">Review findings</a></section>;
}

function Kpi({ label, value, helper, tone = "neutral" }: { label: string; value: number | string; helper: string; tone?: string }) {
  return <article className={`card hc-kpi hc-kpi-${tone}`}><span>{label}</span><strong>{typeof value === "number" ? number.format(value) : value}</strong><small>{helper}</small></article>;
}

function Rules({ rules }: { rules: ReconciliationRule[] }) {
  return (
    <section className="card hc-rules-card" aria-labelledby="rules-heading">
      <div className="card-header"><div><h2 id="rules-heading">Discovered deterministic rules</h2><p className="subtitle">Evidence learned only from confirmed inventory relationships and explicit feedback</p></div><span className="hc-total">{rules.length} rules</span></div>
      {rules.length === 0 ? <div className="empty-state">No rule has enough confirmed evidence yet.</div> : (
        <div className="hc-rule-table" role="table" aria-label="Discovered reconciliation rules">
          <div className="hc-rule-head" role="row"><span>Mapping</span><span>Strength</span><span>Support</span><span>Contradictions</span><span>Evidence examples</span></div>
          {rules.map((rule) => <div className="hc-rule-row" role="row" key={rule.id}><div><code>{rule.source_pattern}</code><span>→</span><code>{rule.target_pattern}</code><small>{rule.transformation}</small></div><span className={`hc-rule-strength hc-rule-${rule.strength.toLowerCase()}`}>{rule.strength.toLowerCase()}</span><strong>{rule.support}</strong><strong>{rule.contradictions}</strong><span className="hc-examples">{rule.examples.slice(0, 2).join(" · ") || "No examples"}</span></div>)}
        </div>
      )}
    </section>
  );
}

function Loading() {
  return <section className="card hc-loading" aria-busy="true"><p role="status">Loading reconciliation summary…</p><div className="hc-skeleton hc-skeleton-heading" /><div className="hc-skeleton hc-skeleton-chart" /><div className="hc-skeleton hc-skeleton-row" /></section>;
}
