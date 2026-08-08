import { useCallback, useEffect, useState, type FormEvent } from "react";

import { fetchHostCompletionAnalytics, saveManualRule } from "./api";
import type { HostCompletionAnalytics, ReconciliationRule } from "./types";

interface Props { endpoint: string; canManageRules?: boolean; }

const number = new Intl.NumberFormat();

export function HostCompletionAnalyticsPage({ endpoint, canManageRules = false }: Props) {
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
      <Rules rules={analytics.rules} canManageRules={canManageRules} onSaved={load} />
    </>
  );
}

function Header() {
  return <section className="page-header"><div><p className="eyebrow">Inventory reconciliation</p><h1>Host Completion</h1><p className="subtitle">Measure explainable OS/BMC reconciliation without forced matches.</p></div><a className="btn btn-primary" href="/host-completion/review">Review findings</a></section>;
}

function Kpi({ label, value, helper, tone = "neutral" }: { label: string; value: number | string; helper: string; tone?: string }) {
  return <article className={`card hc-kpi hc-kpi-${tone}`}><span>{label}</span><strong>{typeof value === "number" ? number.format(value) : value}</strong><small>{helper}</small></article>;
}

function Rules({ rules, canManageRules, onSaved }: { rules: ReconciliationRule[]; canManageRules: boolean; onSaved: () => Promise<void> }) {
  const [editing, setEditing] = useState<ReconciliationRule | "new" | null>(null);
  return <section className="card hc-rules-card" aria-labelledby="rules-heading">
    <div className="card-header"><div><h2 id="rules-heading">Deterministic rules</h2><p className="subtitle">Learned rules are evidence-based; managed rules are explicit administrator policy.</p></div><div className="hc-rule-actions"><span className="hc-total">{rules.length} rules</span>{canManageRules ? <button className="btn btn-primary" type="button" onClick={() => setEditing("new")}>Add rule</button> : null}</div></div>
    {editing ? <RuleEditor rule={editing === "new" ? null : editing} onCancel={() => setEditing(null)} onSaved={async () => { setEditing(null); await onSaved(); }} /> : null}
    {rules.length === 0 ? <div className="empty-state">No rule has enough confirmed evidence yet.</div> : <div className={`hc-rule-table${canManageRules ? " hc-rule-table-managed" : ""}`} role="table" aria-label="Discovered reconciliation rules">
      <div className="hc-rule-head" role="row"><span>Mapping</span><span>Type / strength</span><span>Support</span><span>Contradictions</span><span>Evidence / notes</span>{canManageRules ? <span>Actions</span> : null}</div>
      {rules.map((rule) => <div className="hc-rule-row" role="row" key={rule.id}><div><code>{rule.source_pattern}</code><span>→</span><code>{rule.target_pattern}</code><small>{rule.transformation}</small></div><div><span className={`hc-rule-strength hc-rule-${rule.strength.toLowerCase()}`}>{rule.managed ? (rule.active ? "managed" : "disabled") : rule.strength.toLowerCase()}</span></div><strong>{rule.managed ? "—" : rule.support}</strong><strong>{rule.managed ? "—" : rule.contradictions}</strong><span className="hc-examples">{rule.managed ? rule.notes || "Administrator-managed mapping" : rule.examples.slice(0, 2).join(" · ") || "No examples"}</span>{canManageRules ? <div className="hc-row-action">{rule.managed ? <button className="btn btn-outline btn-small" type="button" onClick={() => setEditing(rule)}>Edit</button> : <span className="hc-muted">Learned</span>}</div> : null}</div>)}
    </div>}
  </section>;
}

function RuleEditor({ rule, onCancel, onSaved }: { rule: ReconciliationRule | null; onCancel: () => void; onSaved: () => Promise<void> }) {
  const [source, setSource] = useState(rule?.source_pattern ?? "");
  const [target, setTarget] = useState(rule?.target_pattern ?? "");
  const [notes, setNotes] = useState(rule?.notes ?? "");
  const [active, setActive] = useState(rule?.active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(null);
    try {
      await saveManualRule({ source_prefix: source, target_prefix: target, active, notes: notes || null }, rule?.manual_rule_id ?? undefined);
      await onSaved();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save the rule."); }
    finally { setSaving(false); }
  }
  return <form className="hc-rule-editor" onSubmit={submit} aria-label={rule ? "Edit managed rule" : "Add managed rule"}>
    <div><label htmlFor="hc-source-prefix">Source prefix</label><input id="hc-source-prefix" required placeholder="10.10.0.0/16" value={source} onChange={(event) => setSource(event.target.value)} /></div>
    <div><label htmlFor="hc-target-prefix">Target prefix</label><input id="hc-target-prefix" required placeholder="10.30.0.0/16" value={target} onChange={(event) => setTarget(event.target.value)} /></div>
    <div><label htmlFor="hc-rule-notes">Note <span>(optional)</span></label><input id="hc-rule-notes" value={notes} onChange={(event) => setNotes(event.target.value)} /></div>
    <label className="hc-active-toggle"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Active</label>
    <div className="hc-editor-actions"><button className="btn btn-primary" disabled={saving} type="submit">{saving ? "Saving…" : rule ? "Save rule" : "Add rule"}</button><button className="btn btn-outline" type="button" onClick={onCancel}>Cancel</button></div>
    <p className="hc-editor-help">Use matching IPv4 `/16` or `/24` networks. Deactivating a rule preserves its history and stops it from generating proposals.</p>
    {error ? <p className="hc-editor-error" role="alert">{error}</p> : null}
  </form>;
}

function Loading() {
  return <section className="card hc-loading" aria-busy="true"><p role="status">Loading reconciliation summary…</p><div className="hc-skeleton hc-skeleton-heading" /><div className="hc-skeleton hc-skeleton-chart" /><div className="hc-skeleton hc-skeleton-row" /></section>;
}
