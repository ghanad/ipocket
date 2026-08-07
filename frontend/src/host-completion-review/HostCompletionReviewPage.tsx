import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../shared/apiClient";
import {
  fetchHostCompletionReviewQueue,
  submitHostCompletionDecision,
} from "./api";
import type {
  HostCompletionDecisionPayload,
  HostCompletionReviewQueue,
  ReconciliationDecision,
  ReconciliationFinding,
} from "./types";

interface Props {
  queueEndpoint: string;
  decisionsEndpoint: string;
}

interface ToastState {
  type: "success" | "error";
  message: string;
}

const findingCopy = {
  CREATE_HOST: {
    eyebrow: "Host creation proposed",
    title: "Create and connect this physical Host",
    action: "Create Host and attach assets",
  },
  COMPLETE_HOST: {
    eyebrow: "Existing Host incomplete",
    title: "Attach the missing relationship",
    action: "Attach missing asset",
  },
  UNMATCHED_ASSET: {
    eyebrow: "Manual investigation",
    title: "No safe counterpart was found",
    action: "",
  },
  CONFLICT: {
    eyebrow: "Inventory conflict",
    title: "Resolve this conflict manually",
    action: "",
  },
} as const;

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The decision could not be saved. Please try again.";
}

function successMessage(decision: ReconciliationDecision): string {
  const messages: Record<ReconciliationDecision, string> = {
    ACCEPT: "Proposal applied.",
    CORRECT: "Corrected relationship applied.",
    WRONG_PAIR: "Wrong pair recorded as rule evidence.",
    UNSURE: "Finding left unresolved for later review.",
    EXCEPTION: "Asset classified as an explicit exception.",
    ATTACH_EXISTING: "Asset attached to the selected Host.",
    DEACTIVATE: "Asset archived.",
  };
  return messages[decision];
}

export function HostCompletionReviewPage({ queueEndpoint, decisionsEndpoint }: Props) {
  const [queue, setQueue] = useState<HostCompletionReviewQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [counterpartIp, setCounterpartIp] = useState("");
  const [showCorrection, setShowCorrection] = useState(false);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setQueue(await fetchHostCompletionReviewQueue(queueEndpoint));
      setCounterpartIp("");
      setShowCorrection(false);
    } catch {
      setQueue(null);
      setLoadError("The reconciliation queue could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [queueEndpoint]);

  useEffect(() => { void loadQueue(); }, [loadQueue]);
  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 4_000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const submit = useCallback(async (
    item: ReconciliationFinding,
    decision: ReconciliationDecision,
    extra: Partial<HostCompletionDecisionPayload> = {},
  ) => {
    if (saving) return;
    setSaving(true);
    setToast(null);
    try {
      await submitHostCompletionDecision(decisionsEndpoint, {
        proposal_id: item.proposal_id,
        inventory_fingerprint: item.inventory_fingerprint,
        decision,
        ...extra,
      });
      setToast({ type: "success", message: successMessage(decision) });
      await loadQueue();
    } catch (error) {
      setToast({ type: "error", message: errorMessage(error) });
    } finally {
      setSaving(false);
    }
  }, [decisionsEndpoint, loadQueue, saving]);

  const item = queue?.item ?? null;
  return (
    <>
      <section className="page-header hcr-page-header">
        <div>
          <p className="eyebrow">Inventory reconciliation</p>
          <h1>Host Completion</h1>
          <p className="subtitle">Review deterministic OS/BMC findings before inventory changes.</p>
        </div>
        <a className="btn btn-outline" href="/host-completion/analytics">View reconciliation summary</a>
      </section>

      {toast ? (
        <div className="toast-container" role="status" aria-live="polite">
          <div className={`toast toast-${toast.type}`}>
            <span className="toast-message">{toast.message}</span>
            <button className="toast-close" type="button" aria-label="Dismiss notification" onClick={() => setToast(null)}>×</button>
          </div>
        </div>
      ) : null}

      <section className="hcr-workbench" aria-label="Host reconciliation queue" aria-live="polite">
        {loading ? <LoadingState /> : null}
        {!loading && loadError ? (
          <section className="card hcr-state-card">
            <div><h2>Unable to load reconciliation queue</h2><p className="subtitle" role="alert">{loadError}</p></div>
            <button className="btn btn-primary" type="button" onClick={() => void loadQueue()}>Try again</button>
          </section>
        ) : null}
        {!loading && !loadError && !item ? (
          <section className="card hcr-empty-state" role="status">
            <span className="hcr-empty-mark" aria-hidden="true">✓</span>
            <h2>No unexplained findings</h2>
            <p className="subtitle">Every active OS/BMC asset is resolved, proposed, or explicitly excepted.</p>
          </section>
        ) : null}
        {!loading && !loadError && item ? (
          <FindingCard
            item={item}
            remaining={queue?.remaining ?? 0}
            saving={saving}
            counterpartIp={counterpartIp}
            showCorrection={showCorrection}
            setCounterpartIp={setCounterpartIp}
            setShowCorrection={setShowCorrection}
            onDecision={(decision, extra) => void submit(item, decision, extra)}
          />
        ) : null}
      </section>
    </>
  );
}

interface FindingCardProps {
  item: ReconciliationFinding;
  remaining: number;
  saving: boolean;
  counterpartIp: string;
  showCorrection: boolean;
  setCounterpartIp: (value: string) => void;
  setShowCorrection: (value: boolean) => void;
  onDecision: (decision: ReconciliationDecision, extra?: Partial<HostCompletionDecisionPayload>) => void;
}

function FindingCard(props: FindingCardProps) {
  const { item, remaining, saving, counterpartIp, showCorrection,
    setCounterpartIp, setShowCorrection, onDecision } = props;
  const copy = findingCopy[item.finding_type];
  const canAccept = item.finding_type === "CREATE_HOST" || item.finding_type === "COMPLETE_HOST";
  const hasPair = item.assets.some((asset) => asset.type === "OS") && item.assets.some((asset) => asset.type === "BMC");
  const subject = item.finding_type === "COMPLETE_HOST"
    ? item.assets.find((asset) => asset.host_id === item.host_id) ?? item.assets[0]
    : item.finding_type === "UNMATCHED_ASSET"
      ? item.assets[0]
      : item.assets.find((asset) => asset.type === "OS") ?? item.assets[0];
  const counterpartType = subject?.type === "BMC" ? "OS" : "BMC";
  const manualEntryVisible = showCorrection || !canAccept;
  return (
    <article className={`card hcr-review-card hcr-${item.state.toLowerCase()}`} aria-busy={saving}>
      <header className="hcr-card-header">
        <div><p className="hcr-host-label">{copy.eyebrow}</p><h2>{copy.title}</h2></div>
        <span className="hcr-remaining">{remaining} remaining</span>
      </header>

      <div className="hcr-reconciliation-grid">
        <section className="hcr-inventory-panel" aria-labelledby="inventory-heading">
          <h3 id="inventory-heading">Inventory facts</h3>
          <div className="hcr-asset-list">
            {item.assets.map((asset) => (
              <div className="hcr-asset-row" key={asset.id}>
                <span className={`hcr-type hcr-type-${asset.type.toLowerCase()}`}>{asset.type}</span>
                <code>{asset.ip_address}</code>
                <span>{asset.host_id ? `Host #${asset.host_id}` : "Unlinked"}</span>
              </div>
            ))}
          </div>
          {item.proposed_host_name ? (
            <div className="hcr-outcome">
              <span>Proposed result</span>
              <strong>Create {item.proposed_host_name}</strong>
              <small>Attach both active assets in one transaction</small>
            </div>
          ) : item.host_id ? (
            <div className="hcr-outcome"><span>Proposed result</span><strong>Complete Host #{item.host_id}</strong></div>
          ) : null}
        </section>

        <section className="hcr-evidence-panel" aria-labelledby="evidence-heading">
          <div className="hcr-evidence-title">
            <h3 id="evidence-heading">Why this finding exists</h3>
            {item.match_strength ? <span className="hcr-strength">{item.match_strength.toLowerCase()} match</span> : null}
          </div>
          {[...item.reasons, ...item.evidence].map((line) => <p key={line}>{line}</p>)}
          {item.evidence.length === 0 ? <p>No deterministic rule supplied enough evidence for an automatic proposal.</p> : null}
        </section>
      </div>

      <footer className="hcr-actions">
        {canAccept ? <button className="btn btn-primary" type="button" disabled={saving} onClick={() => onDecision("ACCEPT")}>{copy.action}</button> : null}
        {hasPair ? <button className="btn btn-outline" type="button" disabled={saving} onClick={() => onDecision("WRONG_PAIR")}>Wrong pair</button> : null}
        {canAccept ? <button className="btn btn-outline" type="button" disabled={saving} onClick={() => setShowCorrection(!showCorrection)}>Use a different counterpart</button> : null}
        <button className="btn btn-outline" type="button" disabled={saving} onClick={() => onDecision("EXCEPTION")}>Mark exception</button>
        <button className="btn hcr-later-button" type="button" disabled={saving} onClick={() => onDecision("UNSURE")}>Review later</button>
      </footer>

      {manualEntryVisible ? (
        <section className="hcr-manual-panel">
          <div className="hcr-counterpart-question">
            <strong>What is the {counterpartType} address for this {subject?.type}?</strong>
            <span>{subject?.ip_address}</span>
            <small>{item.host_id
              ? <>ipocket will attach it to existing Host #{item.host_id} in one transaction.</>
              : <>ipocket will create or reuse <code>{counterpartType === "BMC" ? `server_${counterpartIp || "<bmc-ip>"}` : `server_${subject?.ip_address}`}</code> and attach both assets.</>}</small>
          </div>
          <label className="field"><span>{counterpartType} IP address</span><input className="input" type="text" inputMode="decimal" autoComplete="off" placeholder={counterpartType === "BMC" ? "10.30.4.42" : "10.10.4.42"} value={counterpartIp} onChange={(event) => setCounterpartIp(event.target.value)} /></label>
          <button className="btn btn-primary" type="button" disabled={saving || !counterpartIp.trim()} onClick={() => onDecision("CORRECT", { counterpart_ip: counterpartIp.trim(), counterpart_type: counterpartType })}>Link {counterpartType} and update Host</button>
          {item.finding_type === "UNMATCHED_ASSET" ? <button className="btn btn-danger" type="button" disabled={saving} onClick={() => onDecision("DEACTIVATE")}>Archive asset</button> : null}
        </section>
      ) : null}
    </article>
  );
}

function LoadingState() {
  return (
    <section className="card hcr-review-card hcr-loading" aria-busy="true">
      <p role="status">Loading reconciliation findings…</p>
      <div className="hcr-skeleton hcr-skeleton-title" />
      <div className="hcr-skeleton hcr-skeleton-question" />
      <div className="hcr-skeleton hcr-skeleton-control" />
    </section>
  );
}
