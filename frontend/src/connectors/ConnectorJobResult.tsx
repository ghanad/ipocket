import { useEffect, useRef } from "react";
import type { ConnectorJob } from "./types";

export function ConnectorJobResult({ job, pollError, onRetry }: { job?: ConnectorJob; pollError?: string; onRetry: () => void }) {
  const logRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const log = logRef.current;
    if (log && log.scrollHeight - log.scrollTop - log.clientHeight < 80) log.scrollTop = log.scrollHeight;
  }, [job?.logs]);
  if (!job && !pollError) return null;
  return <div aria-live="polite" role="status" className="connector-log-wrap">
    {job && <p className="label">Status: {job.status}</p>}
    {pollError && <div className="alert alert-error"><p>{pollError}</p><button type="button" className="btn btn-secondary" onClick={onRetry}>Retry polling</button></div>}
    {job?.toast_messages.map((toast, index) => <p className={`alert toast-${toast.type}`} key={`${toast.message}-${index}`}>{toast.message}</p>)}
    {job && job.logs.length > 0 && <><p className="label">Execution log</p><pre ref={logRef} className="connector-log" data-connector-log><code>{job.logs.join("\n")}</code></pre></>}
  </div>;
}
