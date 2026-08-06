/*
THESIS: Host Completion review is a focused decision loop, not a dense queue.
OWN-WORLD: Inherit ipocket's white operational surfaces, blue primary action,
compact metadata, and restrained semantic green, amber, and red states.
STORY: Identify one Host, answer one BMC question, and immediately move forward.
FIRST VIEWPORT: A compact header leads into one centered review card whose Host
identity, progress, evidence, and controls stay visible without scrolling.
FORM: A one-at-a-time operations workbench using incumbent cards and controls;
the precisely specified workflow does not require concept staging or a seed.
*/
import { type CSSProperties, type FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError } from "../shared/apiClient";
import {
  fetchHostCompletionReviewQueue,
  submitHostCompletionDecision,
} from "./api";
import type {
  HostCompletionDecision,
  HostCompletionDecisionPayload,
  HostCompletionReviewItem,
  HostCompletionReviewQueue,
  HostCompletionHostOption,
} from "./types";

interface HostCompletionReviewPageProps {
  queueEndpoint: string;
  decisionsEndpoint: string;
}

interface ToastState {
  type: "success" | "error";
  message: string;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The decision could not be saved. Please try again.";
}

function confidencePercent(confidence: number | null): number {
  if (confidence === null) return 0;
  return Math.round(Math.max(0, Math.min(confidence * 100, 100)));
}

function decisionSuccessMessage(decision: HostCompletionDecision): string {
  switch (decision) {
    case "ACCEPT":
      return "Suggested BMC IP saved.";
    case "REJECT":
      return "Suggestion rejected.";
    case "CORRECTED":
      return "BMC IP saved.";
    case "UNSURE":
      return "Host moved to later.";
    case "NO_BMC":
      return "Host marked as having no BMC.";
    case "NO_OS":
      return "Host marked as having no OS.";
    case "CREATE_HOST_ONLY":
      return "Host created and asset linked.";
    case "ATTACH_EXISTING":
      return "Assets linked to the selected host.";
    case "DEACTIVATE":
      return "Asset deactivated.";
  }
}

export function HostCompletionReviewPage({
  queueEndpoint,
  decisionsEndpoint,
}: HostCompletionReviewPageProps) {
  const [queue, setQueue] = useState<HostCompletionReviewQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [askIp, setAskIp] = useState("");
  const [correctIp, setCorrectIp] = useState("");
  const [correcting, setCorrecting] = useState(false);
  const [hostName, setHostName] = useState("");
  const [hostNameManual, setHostNameManual] = useState(false);
  const [selectedHost, setSelectedHost] = useState<HostCompletionHostOption | null>(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const nextQueue = await fetchHostCompletionReviewQueue(queueEndpoint);
      setQueue(nextQueue);
      setAskIp("");
      setCorrectIp("");
      setHostName("");
      setHostNameManual(false);
      setSelectedHost(null);
      setCorrecting(false);
    } catch {
      setQueue(null);
      setLoadError("The review queue could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [queueEndpoint]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 4_000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const item = queue?.item ?? null;
  const templateBmc = item?.bmc_asset?.address
    ?? (item?.case_type === "HOST_MISSING_BMC" ? item.candidate_ip : null)
    ?? (item?.case_type === "UNLINKED_OS" ? askIp.trim() : null);

  useEffect(() => {
    if (!item || !templateBmc || hostNameManual || selectedHost) return;
    setHostName((item.host_name_template ?? "server_{bmc}").replace("{bmc}", templateBmc));
  }, [hostNameManual, item, selectedHost, templateBmc]);

  const submitDecision = useCallback(
    async (payload: HostCompletionDecisionPayload) => {
      if (saving) return;
      setSaving(true);
      setToast(null);
      try {
        const response = await submitHostCompletionDecision(decisionsEndpoint, payload);
        setToast({
          type: "success",
          message: response.message ?? decisionSuccessMessage(payload.decision),
        });
        await loadQueue();
      } catch (error) {
        setToast({ type: "error", message: errorMessage(error) });
      } finally {
        setSaving(false);
      }
    },
    [decisionsEndpoint, loadQueue, saving],
  );

  function sharedPayload(item: HostCompletionReviewItem) {
    return {
      case_type: item.case_type,
      mode: item.mode,
      ...(item.host_id ? { host_id: item.host_id } : {}),
      ...(item.os_asset ? { os_address: item.os_asset.address } : {}),
      ...(item.bmc_asset ? { bmc_address: item.bmc_asset.address } : {}),
      ...(item.candidate_ip ? { candidate_ip: item.candidate_ip } : {}),
      ...(item.would_create_host && hostName.trim()
        ? { host_name: hostName.trim() }
        : {}),
    };
  }

  function submitIp(
    event: FormEvent<HTMLFormElement>,
    item: HostCompletionReviewItem,
    value: string,
  ) {
    event.preventDefault();
    const correctedIp = value.trim();
    if (!correctedIp) return;
    void submitDecision({
      ...sharedPayload(item),
      decision: "CORRECTED",
      corrected_ip: correctedIp,
    });
  }

  return (
    <>
      <section className="page-header hcr-page-header">
        <div>
          <p className="eyebrow">Host Completion</p>
          <h1>Review Hosts</h1>
          <p className="subtitle">Resolve missing BMC relationships one host at a time.</p>
        </div>
        <a className="btn btn-outline" href="/host-completion/analytics">
          View analytics
        </a>
      </section>

      {toast ? (
        <div className="toast-container" role="status" aria-live="polite">
          <div className={`toast toast-${toast.type}`}>
            <span className="toast-message">{toast.message}</span>
            <button
              className="toast-close"
              type="button"
              aria-label="Dismiss notification"
              onClick={() => setToast(null)}
            >
              ×
            </button>
          </div>
        </div>
      ) : null}

      <section
        className="hcr-workbench"
        aria-label="Host Completion review queue"
        aria-live="polite"
      >
        {loading ? <ReviewLoadingState /> : null}

        {!loading && loadError ? (
          <section className="card hcr-state-card">
            <div>
              <h2>Unable to load review queue</h2>
              <p className="subtitle" role="alert">{loadError}</p>
            </div>
            <button className="btn btn-primary" type="button" onClick={() => void loadQueue()}>
              Try again
            </button>
          </section>
        ) : null}

        {!loading && !loadError && !item ? (
          <section className="card hcr-empty-state" role="status">
            <span className="hcr-empty-mark" aria-hidden="true">✓</span>
            <h2>No more cases 🎉</h2>
            <p className="subtitle">Every eligible Host has been reviewed.</p>
          </section>
        ) : null}

        {!loading && !loadError && item ? (
          <ReviewCard
            item={item}
            remaining={queue?.remaining ?? 0}
            saving={saving}
            askIp={askIp}
            setAskIp={setAskIp}
            correctIp={correctIp}
            setCorrectIp={setCorrectIp}
            correcting={correcting}
            setCorrecting={setCorrecting}
            hostName={hostName}
            onHostNameChange={(value) => {
              setHostName(value);
              setHostNameManual(true);
              setSelectedHost(null);
            }}
            selectedHost={selectedHost}
            onHostOptionSelect={(option) => {
              setHostName(option.name);
              setSelectedHost(option);
              setHostNameManual(true);
            }}
            onSubmitIp={submitIp}
            onDecision={(decision) =>
              void submitDecision({ ...sharedPayload(item), decision })
            }
            onAttachExisting={(option) => void submitDecision({
              ...sharedPayload(item),
              decision: "ATTACH_EXISTING",
              target_host_id: option.id,
            })}
          />
        ) : null}
      </section>
    </>
  );
}

interface ReviewCardProps {
  item: HostCompletionReviewItem;
  remaining: number;
  saving: boolean;
  askIp: string;
  setAskIp: (value: string) => void;
  correctIp: string;
  setCorrectIp: (value: string) => void;
  correcting: boolean;
  setCorrecting: (value: boolean) => void;
  hostName: string;
  onHostNameChange: (value: string) => void;
  selectedHost: HostCompletionHostOption | null;
  onHostOptionSelect: (option: HostCompletionHostOption) => void;
  onSubmitIp: (
    event: FormEvent<HTMLFormElement>,
    item: HostCompletionReviewItem,
    value: string,
  ) => void;
  onDecision: (decision: Exclude<HostCompletionDecision, "CORRECTED">) => void;
  onAttachExisting: (option: HostCompletionHostOption) => void;
}

function ReviewCard({
  item,
  remaining,
  saving,
  askIp,
  setAskIp,
  correctIp,
  setCorrectIp,
  correcting,
  setCorrecting,
  hostName,
  onHostNameChange,
  selectedHost,
  onHostOptionSelect,
  onSubmitIp,
  onDecision,
  onAttachExisting,
}: ReviewCardProps) {
  const confidence = confidencePercent(item.confidence);
  const knownAsset = item.os_asset ?? item.bmc_asset;
  const missingLabel = item.case_type.endsWith("BMC") || item.case_type === "UNLINKED_OS"
    ? "BMC"
    : "OS";
  const noSideDecision = missingLabel === "BMC" ? "NO_BMC" : "NO_OS";
  const needsHostName = item.would_create_host;
  const hostTemplate = item.host_name_template ?? "server_{bmc}";
  const hostOptions = item.host_options ?? [];
  const missingSideAlreadyPresent = selectedHost && (
    missingLabel === "BMC" ? selectedHost.has_bmc : selectedHost.has_os
  );
  const hasPair = Boolean(item.os_asset && item.bmc_asset);

  return (
    <article className="card hcr-review-card" aria-busy={saving}>
      <header className="hcr-card-header">
        <div>
          <p className="hcr-host-label">{item.host_id ? "Existing host" : "Unlinked assets"}</p>
          <h2>{item.host_id ? `Host #${item.host_id}` : "Create a host relationship"}</h2>
          {knownAsset ? <p className="hcr-os-ip"><span>Known address</span>{knownAsset.address}</p> : null}
        </div>
        <span className="hcr-remaining">remaining: {remaining}</span>
      </header>

      <div className="hcr-divider" />

      {needsHostName ? (
        <label className="field hcr-host-name-field">
          <span>Host name</span>
          <input
            className="input"
            type="text"
            autoComplete="off"
            placeholder={`e.g. ${hostTemplate.replace("{bmc}", "10.30.1.1")}`}
            value={hostName}
            onChange={(event) => {
              const value = event.target.value;
              onHostNameChange(value);
              const option = hostOptions.find((candidate) => candidate.name.toLowerCase() === value.trim().toLowerCase());
              if (option) onHostOptionSelect(option);
            }}
            list="host-completion-host-options"
            disabled={saving}
            required
          />
          <datalist id="host-completion-host-options">
            {hostOptions.map((option) => <option key={option.id} value={option.name} />)}
          </datalist>
        </label>
      ) : null}

      {hasPair ? <p className="hcr-pair-summary">Pair ready: OS {item.os_asset?.address} and BMC {item.bmc_asset?.address}.</p> : null}

      {missingSideAlreadyPresent ? (
        <section className="hcr-decision-panel" aria-labelledby="attach-question">
          <p className="hcr-mode-label">Existing host selected</p>
          <h3 id="attach-question">Attach this case to {selectedHost.name}?</h3>
          <p className="hcr-reason">That host already has the {missingLabel} side, so no address is needed.</p>
          <div className="hcr-suggestion-actions">
            <button className="btn btn-primary" type="button" disabled={saving} onClick={() => onAttachExisting(selectedHost)}>Attach to host</button>
            <button className="btn hcr-later-button" type="button" disabled={saving} onClick={() => onDecision("UNSURE")}>Later</button>
          </div>
        </section>
      ) : item.mode === "ASK" ? (
        <section className="hcr-decision-panel" aria-labelledby="ask-question">
          <p className="hcr-mode-label">Address needed</p>
          <h3 id="ask-question">What is the {missingLabel} IP for this case?</h3>
          <form className="hcr-ip-form" onSubmit={(event) => onSubmitIp(event, item, askIp)}>
            <label className="field">
              <span>{missingLabel} IP address</span>
              <input
                className="input"
                type="text"
                inputMode="decimal"
                autoComplete="off"
                placeholder="192.0.2.10"
                value={askIp}
                onChange={(event) => setAskIp(event.target.value)}
                disabled={saving}
                required
                autoFocus
              />
            </label>
            <button className="btn btn-primary" type="submit" disabled={saving || !askIp.trim() || (needsHostName && !hostName.trim())}>
              {saving ? "Saving…" : "Save"}
            </button>
          </form>
          <div className="hcr-secondary-actions">
            {item.case_type.startsWith("HOST_MISSING") || item.case_type.startsWith("UNLINKED") ? <button className="btn btn-outline" type="button" disabled={saving || (needsHostName && !hostName.trim())} onClick={() => onDecision(noSideDecision)}>No {missingLabel}</button> : null}
            <button className="btn hcr-later-button" type="button" disabled={saving} onClick={() => onDecision("UNSURE")}>Later</button>
          </div>
        </section>
      ) : (
        <section className="hcr-decision-panel" aria-labelledby="suggest-question">
          <p className="hcr-mode-label">Suggested address</p>
          <h3 id="suggest-question">Is this the {missingLabel} IP for this case?</h3>
          <div className="hcr-candidate-block">
            <code>{item.candidate_ip}</code>
            <div className="hcr-confidence-copy">
              <span>Confidence</span>
              <strong>{confidence}%</strong>
            </div>
            <div
              className="hcr-confidence-bar"
              role="progressbar"
              aria-label="Suggestion confidence"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidence}
            >
              <span style={{ "--confidence-width": `${confidence}%` } as CSSProperties} />
            </div>
            <p className="hcr-reason">{item.reason_text}</p>
          </div>

          <div className="hcr-suggestion-actions">
            <button className="btn btn-primary" type="button" disabled={saving || (needsHostName && !hostName.trim())} onClick={() => onDecision("ACCEPT")}>Yes</button>
            <button className="btn btn-outline" type="button" disabled={saving} onClick={() => onDecision("REJECT")}>No</button>
            <button className="btn btn-outline" type="button" disabled={saving} aria-expanded={correcting} onClick={() => setCorrecting(!correcting)}>Correct</button>
            <button className="btn hcr-later-button" type="button" disabled={saving} onClick={() => onDecision("UNSURE")}>Later</button>
            {item.case_type.startsWith("HOST_MISSING") || item.case_type.startsWith("UNLINKED") ? <button className="btn btn-outline" type="button" disabled={saving || (needsHostName && !hostName.trim())} onClick={() => onDecision(noSideDecision)}>No {missingLabel}</button> : null}
          </div>

          {correcting ? (
            <form className="hcr-correct-form" onSubmit={(event) => onSubmitIp(event, item, correctIp)}>
              <label className="field">
                <span>Correct {missingLabel} IP address</span>
                <input
                  className="input"
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="192.0.2.10"
                  value={correctIp}
                  onChange={(event) => setCorrectIp(event.target.value)}
                  disabled={saving}
                  required
                  autoFocus
                />
              </label>
              <button className="btn btn-primary" type="submit" disabled={saving || !correctIp.trim() || (needsHostName && !hostName.trim())}>
                {saving ? "Saving…" : "Save correction"}
              </button>
            </form>
          ) : null}
        </section>
      )}
    </article>
  );
}

function ReviewLoadingState() {
  return (
    <section className="card hcr-review-card hcr-loading" aria-busy="true">
      <p role="status">Loading Host Completion review…</p>
      <div className="hcr-skeleton hcr-skeleton-title" />
      <div className="hcr-skeleton hcr-skeleton-meta" />
      <div className="hcr-skeleton hcr-skeleton-question" />
      <div className="hcr-skeleton hcr-skeleton-control" />
    </section>
  );
}
