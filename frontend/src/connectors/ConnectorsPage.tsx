import { useCallback, useEffect, useRef, useState } from "react";

import { ConnectorApiError, fetchConnectorJob, fetchConnectorsConfig, isConnectorName, jobUrl, runConnector } from "./api";
import { ConnectorForm } from "./ConnectorForm";
import { ConnectorTabs } from "./ConnectorTabs";
import { ConnectorsOverview } from "./ConnectorsOverview";
import { clearSecrets, defaultFormState } from "./connectorSchemas";
import type { ConnectorJob, ConnectorMode, ConnectorName, ConnectorsConfig, ConnectorTab, FieldValue } from "./types";

function locationState(): { tab: ConnectorTab; jobId: string } {
  const params = new URLSearchParams(window.location.search);
  const value = params.get("tab");
  return { tab: value === "overview" || isConnectorName(value) ? value : "overview", jobId: params.get("job_id") ?? "" };
}

function canonicalUrl(tab: ConnectorTab, jobId = ""): string {
  const params = new URLSearchParams({ tab });
  if (jobId) params.set("job_id", jobId);
  return `/ui/connectors?${params}`;
}

export function ConnectorsPage({ endpoint, initialTab = "overview", initialJobId = "" }: { endpoint: string; initialTab?: ConnectorTab; initialJobId?: string }) {
  const [config, setConfig] = useState<ConnectorsConfig | null>(null);
  const [tab, setTab] = useState<ConnectorTab>(initialTab);
  const [forms, setForms] = useState<Partial<Record<ConnectorName, Record<string, FieldValue>>>>({});
  const [jobs, setJobs] = useState<Partial<Record<ConnectorName, ConnectorJob>>>({});
  const [errors, setErrors] = useState<Partial<Record<ConnectorName, string>>>({});
  const [pollErrors, setPollErrors] = useState<Partial<Record<ConnectorName, string>>>({});
  const [submitting, setSubmitting] = useState<ConnectorName | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const activePoll = useRef<{ id: string; controller: AbortController } | null>(null);
  const timer = useRef<number | null>(null);
  const initialJob = useRef(initialJobId);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    activePoll.current?.controller.abort();
    activePoll.current = null;
  }, []);

  const pollJob = useCallback((connector: ConnectorName, id: string, immediate = true) => {
    if (!config) return;
    stopPolling();
    const run = async () => {
      const controller = new AbortController();
      activePoll.current = { id, controller };
      try {
        const job = await fetchConnectorJob(jobUrl(config.jobs_url, id), controller.signal);
        if (activePoll.current?.id !== id) return;
        setJobs((current) => ({ ...current, [connector]: job }));
        setForms((current) => ({ ...current, [connector]: { ...(current[connector] ?? {}), ...job.form_state } }));
        setPollErrors((current) => ({ ...current, [connector]: undefined }));
        if (job.polling) timer.current = window.setTimeout(run, config.poll_interval_ms);
        else activePoll.current = null;
      } catch (error) {
        if (controller.signal.aborted) return;
        const message = error instanceof ConnectorApiError && error.status === 404 ? "Connector job was not found or has expired." : "Polling was interrupted. Retry to continue.";
        setPollErrors((current) => ({ ...current, [connector]: message }));
        activePoll.current = null;
      }
    };
    if (immediate) void run(); else timer.current = window.setTimeout(run, config.poll_interval_ms);
  }, [config, stopPolling]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchConnectorsConfig(endpoint, controller.signal).then((value) => {
      setConfig(value);
      setForms(Object.fromEntries(value.connectors.map((schema) => [schema.name, defaultFormState(schema)])));
    }).catch((error) => { if (!controller.signal.aborted) setLoadError(error instanceof Error ? error.message : "Unable to load connector configuration."); });
    return () => controller.abort();
  }, [endpoint]);

  useEffect(() => {
    if (!config || !initialJob.current || !isConnectorName(tab)) return;
    const id = initialJob.current; initialJob.current = ""; pollJob(tab, id);
  }, [config, pollJob, tab]);

  useEffect(() => {
    const onPopState = () => {
      const next = locationState();
      setTab((current) => {
        if (config && isConnectorName(current)) {
          const schema = config.connectors.find((item) => item.name === current)!;
          setForms((forms) => ({ ...forms, [current]: clearSecrets(schema, forms[current] ?? {}) }));
        }
        return next.tab;
      });
      stopPolling();
      if (config && next.jobId && isConnectorName(next.tab)) pollJob(next.tab, next.jobId);
    };
    window.addEventListener("popstate", onPopState);
    return () => { window.removeEventListener("popstate", onPopState); stopPolling(); };
  }, [config, pollJob, stopPolling]);

  const selectTab = (next: ConnectorTab) => {
    if (config && isConnectorName(tab)) {
      const schema = config.connectors.find((item) => item.name === tab)!;
      setForms((current) => ({ ...current, [tab]: clearSecrets(schema, current[tab] ?? {}) }));
    }
    stopPolling(); setTab(next);
    const id = isConnectorName(next) ? jobs[next]?.job_id ?? "" : "";
    window.history.pushState({}, "", canonicalUrl(next, id));
    if (id && isConnectorName(next) && jobs[next]?.polling) pollJob(next, id);
  };

  const submit = async (connector: ConnectorName, mode: ConnectorMode) => {
    if (!config || submitting !== null) return;
    if (mode === "apply") {
      if (!config.policy.can_apply) return;
      if (!window.confirm("Apply this connector import? Inventory records may be created or updated.")) return;
    }
    const schema = config.connectors.find((item) => item.name === connector)!;
    const values = forms[connector] ?? defaultFormState(schema);
    setSubmitting(connector); setErrors((current) => ({ ...current, [connector]: undefined }));
    try {
      const started = await runConnector(schema.run_url, { ...values, mode });
      setForms((current) => ({ ...current, [connector]: clearSecrets(schema, current[connector] ?? {}) }));
      setJobs((current) => ({ ...current, [connector]: { job_id: started.job_id, connector, active_tab: connector, status: "queued", form_state: {}, logs: [], toast_messages: [], polling: true } }));
      window.history.replaceState({}, "", canonicalUrl(connector, started.job_id));
      pollJob(connector, started.job_id, false);
    } catch (error) {
      const message = error instanceof ConnectorApiError ? error.message : "Unable to start the connector. No credentials were retained.";
      setErrors((current) => ({ ...current, [connector]: message }));
      setForms((current) => ({ ...current, [connector]: clearSecrets(schema, current[connector] ?? {}) }));
    } finally { setSubmitting(null); }
  };

  if (loadError) return <section className="card empty-state" role="alert">{loadError}</section>;
  if (!config) return <section className="card empty-state" role="status">Loading Connectors…</section>;
  const schema = isConnectorName(tab) ? config.connectors.find((item) => item.name === tab) : undefined;
  return <>
    <section className="page-header"><div><p className="eyebrow">Connectors</p><h1>Integrations</h1><p className="subtitle">Manage external inventory connectors and import flow guidance.</p></div></section>
    <ConnectorTabs connectors={config.connectors} active={tab} onSelect={selectTab} />
    {tab === "overview" ? <ConnectorsOverview connectors={config.connectors} onSelect={selectTab} /> : schema && <ConnectorForm schema={schema} values={forms[schema.name] ?? defaultFormState(schema)} canApply={config.policy.can_apply} submitting={submitting === schema.name} error={errors[schema.name]} job={jobs[schema.name]} pollError={pollErrors[schema.name]} onChange={(name, value) => setForms((current) => ({ ...current, [schema.name]: { ...(current[schema.name] ?? {}), [name]: value } }))} onSubmit={(mode) => void submit(schema.name, mode)} onRetry={() => { const id = jobs[schema.name]?.job_id; if (id) pollJob(schema.name, id); }} />}
  </>;
}
