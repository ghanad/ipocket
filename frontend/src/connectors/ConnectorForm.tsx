import { useMemo } from "react";
import { ConnectorField } from "./ConnectorField";
import { ConnectorJobResult } from "./ConnectorJobResult";
import type { ConnectorJob, ConnectorMode, ConnectorSchema, FieldValue } from "./types";

export function ConnectorForm({ schema, values, canApply, submitting, error, job, pollError, onChange, onSubmit, onRetry }: {
  schema: ConnectorSchema; values: Record<string, FieldValue>; canApply: boolean; submitting: boolean; error?: string; job?: ConnectorJob; pollError?: string;
  onChange: (name: string, value: FieldValue) => void; onSubmit: (mode: ConnectorMode) => void; onRetry: () => void;
}) {
  const fields = schema.fields.filter((field) => field.name !== "mode");
  const ready = useMemo(() => fields.every((field) => !field.required || field.type === "checkbox" || String(values[field.name] ?? "").trim().length > 0), [fields, values]);
  const running = job?.polling === true;
  return <div id={`connector-panel-${schema.name}`} role="tabpanel" aria-labelledby={`connector-tab-${schema.name}`}>
    <section className="card connector-run-card"><div className="card-header card-header-padded"><div><h2>Run {schema.display_name} Connector</h2><p className="subtitle">{schema.description}</p></div></div>
      <div className="card-body"><form className="form-grid form-grid-two connector-form" aria-label={`${schema.display_name} connector`} onSubmit={(event) => { event.preventDefault(); onSubmit("dry-run"); }}>
        {fields.map((field) => <ConnectorField key={field.name} field={field} value={values[field.name] ?? field.default} disabled={submitting || running} onChange={(value) => onChange(field.name, value)} />)}
        <div className="form-actions field-span">
          <button type="submit" className="btn btn-secondary" disabled={!ready || submitting || running}>{submitting ? "Starting…" : "Dry-run"}</button>
          <button type="button" className="btn btn-primary" disabled={!ready || !canApply || submitting || running} title={!canApply ? "Editor role required to apply connector imports." : undefined} onClick={() => onSubmit("apply")}>Apply</button>
        </div>
        {!canApply && <p className="subtitle field-span">Viewer role can dry-run; Editor role is required to apply.</p>}
      </form>
      {error && <div className="alert alert-error connector-errors" role="alert"><p>{error}</p></div>}
      <ConnectorJobResult job={job} pollError={pollError} onRetry={onRetry} />
      </div>
    </section>
    <section className="card"><div className="card-header card-header-padded"><div><h2>CLI (kept as-is)</h2><p className="subtitle">You can still run this connector manually.</p></div></div><div className="card-body"><pre className="connector-code-block"><code>{schema.command}</code></pre><p>{schema.help}</p></div></section>
  </div>;
}
