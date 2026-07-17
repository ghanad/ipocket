import { type FormEvent, useEffect, useState } from "react";

import {
  DataOpsApiError,
  fetchDataOpsConfig,
  runDataImport,
} from "./api";
import type {
  DataOpsConfig,
  DataOpsTab,
  ImportKind,
  ImportMode,
  ImportResult,
  NmapResult,
} from "./types";

const exportCards = [
  {
    title: "Export All Data",
    description: "Bundle every entity for backup, migration, or re-import.",
    links: [
      ["bundle.zip", "/export/bundle.zip"],
      ["bundle.json", "/export/bundle.json"],
    ],
  },
  {
    title: "Export IP Assets",
    description: "Download addresses, assignments, tags, notes, and archive state.",
    links: [
      ["CSV", "/export/ip-assets.csv"],
      ["JSON", "/export/ip-assets.json"],
    ],
  },
  {
    title: "Export Hosts",
    description: "Download host, vendor, project, OS IP, and BMC IP data.",
    links: [
      ["CSV", "/export/hosts.csv"],
      ["JSON", "/export/hosts.json"],
    ],
  },
];

function StandardResult({ result }: { result: ImportResult }) {
  const rows: Array<[string, ImportResult["summary"]["total"]]> = [
    ["Total", result.summary.total],
    ["Vendors", result.summary.vendors],
    ["Projects", result.summary.projects],
    ["Hosts", result.summary.hosts],
    ["IP Assets", result.summary.ip_assets],
  ];
  return (
    <div className="import-results" aria-live="polite">
      <h3>Summary</h3>
      <ul>
        {rows.map(([label, count]) => (
          <li key={label}>
            {label}: {count.would_create} create, {count.would_update} update, {count.would_skip} skip
          </li>
        ))}
      </ul>
      {result.errors.length > 0 && (
        <IssueList title="Errors" issues={result.errors.map((issue) => `${issue.location}: ${issue.message}`)} />
      )}
      {result.warnings.length > 0 && (
        <IssueList title="Warnings" issues={result.warnings.map((issue) => `${issue.location}: ${issue.message}`)} />
      )}
    </div>
  );
}

function NmapImportResult({ result }: { result: NmapResult }) {
  return (
    <div className="import-results" aria-live="polite">
      <h3>Summary</h3>
      <ul>
        <li>Discovered up hosts: {result.discovered_up_hosts}</li>
        <li>New IPs created: {result.new_ips_created}</li>
        <li>Existing IPs seen: {result.existing_ips_seen}</li>
      </ul>
      {result.errors.length > 0 && <IssueList title="Errors" issues={result.errors} />}
      {result.new_assets.length > 0 && (
        <div>
          <h4>New IP assets</h4>
          <ul>
            {result.new_assets.map((asset) => (
              <li key={asset.id}><a className="link" href={`/ui/ip-assets/${asset.id}`}>{asset.ip_address}</a></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function IssueList({ title, issues }: { title: string; issues: string[] }) {
  return (
    <div className={title === "Errors" ? "import-errors" : "import-warnings"}>
      <h4>{title}</h4>
      <ul>{issues.map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}</ul>
    </div>
  );
}

export function DataOpsPage({
  endpoint,
  importEndpoint,
  initialTab = "import",
}: {
  endpoint: string;
  importEndpoint: string;
  initialTab?: DataOpsTab;
}) {
  const [tab, setTab] = useState<DataOpsTab>(initialTab);
  const [config, setConfig] = useState<DataOpsConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [bundleFile, setBundleFile] = useState<File | null>(null);
  const [hostsFile, setHostsFile] = useState<File | null>(null);
  const [assetsFile, setAssetsFile] = useState<File | null>(null);
  const [nmapFile, setNmapFile] = useState<File | null>(null);
  const [results, setResults] = useState<Partial<Record<ImportKind, ImportResult | NmapResult>>>({});
  const [errors, setErrors] = useState<Partial<Record<ImportKind, string>>>({});
  const [running, setRunning] = useState<ImportKind | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    fetchDataOpsConfig(endpoint)
      .then(setConfig)
      .catch(() => setLoadError("Data Operations could not be loaded. Please try again."));
  }, [endpoint]);

  function selectTab(next: DataOpsTab) {
    setTab(next);
    window.history.replaceState({}, "", `/ui/import?tab=${next}`);
  }

  async function submit(kind: ImportKind, mode: ImportMode, event?: FormEvent) {
    event?.preventDefault();
    if (running) return;
    const form = new FormData();
    if (kind === "bundle" && bundleFile) form.append("file", bundleFile);
    if (kind === "csv" && hostsFile) form.append("hosts", hostsFile);
    if (kind === "csv" && assetsFile) form.append("ip_assets", assetsFile);
    if (kind === "nmap" && nmapFile) form.append("file", nmapFile);
    if ([...form.keys()].length === 0) {
      setErrors((current) => ({ ...current, [kind]: kind === "csv" ? "Select at least one CSV file." : "Select a file." }));
      return;
    }
    setRunning(kind);
    setErrors((current) => ({ ...current, [kind]: undefined }));
    try {
      const result = await runDataImport(importEndpoint, kind, mode, form);
      setResults((current) => ({ ...current, [kind]: result }));
      setToast(`${kind === "nmap" ? "Nmap" : kind === "csv" ? "CSV" : "Bundle"} ${mode === "apply" ? "import applied" : "dry-run completed"}.`);
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [kind]: error instanceof DataOpsApiError ? error.message : "Import request could not be completed.",
      }));
    } finally {
      setRunning(null);
    }
  }

  return (
    <>
      {toast && (
        <div className="toast-container" role="status">
          <div className="toast toast-success"><span className="toast-message">{toast}</span><button className="toast-close" type="button" aria-label="Dismiss notification" onClick={() => setToast(null)}>×</button></div>
        </div>
      )}
      <section className="page-header">
        <div><p className="eyebrow">Data Operations</p><h1>Import &amp; Export</h1><p className="subtitle">Move inventory data in and out from one place.</p></div>
      </section>
      <div className="tabs" role="tablist" aria-label="Data operations sections">
        {(["import", "export"] as const).map((item) => (
          <a key={item} className={`tab${tab === item ? " tab-active" : ""}`} href={`/ui/import?tab=${item}`} role="tab" aria-selected={tab === item} onClick={(event) => { event.preventDefault(); selectTab(item); }}>{item === "import" ? "Import" : "Export"}</a>
        ))}
      </div>
      {loadError ? <section className="card"><p className="alert" role="alert">{loadError}</p></section> : !config ? <section className="card empty-state" role="status">Loading Data Operations…</section> : tab === "export" ? (
        <div className="export-options-grid">
          {exportCards.map((card) => (
            <section className="card export-option-card" key={card.title}>
              <div className="card-header"><div><h2>{card.title}</h2><p className="subtitle">{card.description}</p></div></div>
              <div className="card-body"><div className="export-option-footer"><div className="form-actions">{card.links.map(([label, href], index) => <a key={href} className={`btn ${index ? "btn-primary" : "btn-secondary"}`} href={href}>{label}</a>)}</div></div></div>
            </section>
          ))}
        </div>
      ) : (
        <div className="import-options-grid">
          <ImportCard title="Import Bundle (JSON)" description={`Upload bundle.json (maximum ${config.upload.max_size}).`} kind="bundle" canApply={config.policy.can_apply} running={running} error={errors.bundle} result={results.bundle} onSubmit={submit}>
            <label className="field"><span>bundle.json</span><input className="input" type="file" aria-label="bundle.json" accept="application/json" onChange={(event) => setBundleFile(event.target.files?.[0] ?? null)} /></label>
          </ImportCard>
          <ImportCard title="Import CSV" description="Upload hosts.csv and/or ip-assets.csv exports." kind="csv" canApply={config.policy.can_apply} running={running} error={errors.csv} result={results.csv} onSubmit={submit}>
            <p className="subtitle">Sample files: <a className="link" href={config.samples.hosts} download>hosts.csv</a> and <a className="link" href={config.samples.ip_assets} download>ip-assets.csv</a></p>
            <label className="field"><span>hosts.csv</span><input className="input" type="file" aria-label="hosts.csv" accept="text/csv" onChange={(event) => setHostsFile(event.target.files?.[0] ?? null)} /></label>
            <label className="field"><span>ip-assets.csv</span><input className="input" type="file" aria-label="ip-assets.csv" accept="text/csv" onChange={(event) => setAssetsFile(event.target.files?.[0] ?? null)} /></label>
          </ImportCard>
          <ImportCard title="Upload Nmap XML" description="Import discovered IPv4 hosts without overwriting existing assets." kind="nmap" canApply={config.policy.can_apply} running={running} error={errors.nmap} result={results.nmap} onSubmit={submit}>
            <p className="subtitle"><code>nmap -sn -oX ipocket.xml &lt;CIDR&gt;</code></p>
            <label className="field"><span>Nmap XML file</span><input className="input" type="file" aria-label="Nmap XML file" accept=".xml,application/xml,text/xml" onChange={(event) => setNmapFile(event.target.files?.[0] ?? null)} /></label>
          </ImportCard>
        </div>
      )}
    </>
  );
}

function ImportCard({ title, description, kind, canApply, running, error, result, onSubmit, children }: {
  title: string; description: string; kind: ImportKind; canApply: boolean; running: ImportKind | null; error?: string; result?: ImportResult | NmapResult; onSubmit: (kind: ImportKind, mode: ImportMode, event?: FormEvent) => void; children: React.ReactNode;
}) {
  const busy = running === kind;
  return (
    <section className="card import-option-card">
      <div className="card-header"><div><h2>{title}</h2><p className="subtitle">{description}</p></div></div>
      <div className="card-body">
        <form className="form-grid import-option-form" onSubmit={(event) => void onSubmit(kind, "dry-run", event)}>{children}</form>
        {error && <p className="alert" role="alert">{error}</p>}
        {result && (kind === "nmap" ? <NmapImportResult result={result as NmapResult} /> : <StandardResult result={result as ImportResult} />)}
        <div className="import-option-footer"><div className="form-actions">
          <button className="btn btn-secondary" type="button" disabled={running !== null} onClick={() => void onSubmit(kind, "dry-run")}>{busy ? "Running…" : "Dry-run"}</button>
          <button className="btn btn-primary" type="button" disabled={!canApply || running !== null} title={!canApply ? "Editor role required to apply imports." : undefined} onClick={() => void onSubmit(kind, "apply")}>Apply</button>
        </div>{!canApply && <p className="subtitle">Viewer role can dry-run; Editor role is required to apply.</p>}</div>
      </div>
    </section>
  );
}
