import type { AuditLog } from "./types";

export function AuditLogTable({ logs }: { logs: AuditLog[] }) {
  return (
    <section className="card">
      <h2>Audit Log</h2>
      {logs.length ? (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>User</th>
              <th>Action</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, index) => (
              <tr key={`${log.created_at}-${index}`}>
                <td>{log.created_at}</td>
                <td>{log.user || "System"}</td>
                <td>
                  <span
                    className={`pill ${
                      log.action === "DELETE"
                        ? "pill-danger"
                        : log.action === "CREATE"
                          ? "pill-success"
                          : "pill-warning"
                    }`}
                  >
                    {log.action}
                  </span>
                </td>
                <td>
                  <p className="ip-audit-summary">{log.changes.summary}</p>
                  {log.changes.raw &&
                    log.changes.raw !== log.changes.summary && (
                      <details className="ip-audit-raw">
                        <summary>View details</summary>
                        <pre>{log.changes.raw}</pre>
                      </details>
                    )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No audit history yet.</p>
      )}
    </section>
  );
}
