import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AuditActionBadge } from "../shared/AuditActionBadge";
import { fetchAuditLogs } from "./api";
import type { AuditLogQuery, AuditLogResponse } from "./types";

const PAGE_SIZES = [10, 20, 50, 100];

export function queryFromSearch(search: string): AuditLogQuery {
  const params = new URLSearchParams(search);
  const parsedPage = Number(params.get("page") || 1);
  const parsedPerPage = Number(params.get("per-page") || 20);
  return {
    page:
      Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1,
    per_page: PAGE_SIZES.includes(parsedPerPage) ? parsedPerPage : 20,
  };
}

export function searchFromQuery(query: AuditLogQuery): string {
  const params = new URLSearchParams();
  if (query.page > 1) params.set("page", String(query.page));
  if (query.per_page !== 20) {
    params.set("per-page", String(query.per_page));
  }
  return params.toString();
}

export function AuditLogPage({
  endpoint,
  initialQuery = "",
}: {
  endpoint: string;
  initialQuery?: string;
}) {
  const [queryState, setQueryState] = useState(() =>
    queryFromSearch(initialQuery || window.location.search),
  );
  const [data, setData] = useState<AuditLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const requestId = useRef(0);
  const activeController = useRef<AbortController | null>(null);
  const query = useMemo(() => searchFromQuery(queryState), [queryState]);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    setLoading(true);
    setLoadError(false);
    try {
      const response = await fetchAuditLogs(
        `${endpoint}${query ? `?${query}` : ""}`,
        controller.signal,
      );
      if (id !== requestId.current) return;
      setData(response);
      if (
        response.query.page !== queryState.page ||
        response.query.per_page !== queryState.per_page
      ) {
        setQueryState(response.query);
      }
    } catch (error) {
      if (
        id === requestId.current &&
        !(error instanceof DOMException && error.name === "AbortError")
      ) {
        setLoadError(true);
      }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [endpoint, query, queryState.page, queryState.per_page]);

  useEffect(() => {
    void load();
    return () => activeController.current?.abort();
  }, [load]);

  useEffect(() => {
    const next = query ? `/ui/audit-log?${query}` : "/ui/audit-log";
    if (`${window.location.pathname}${window.location.search}` !== next) {
      window.history.pushState({}, "", next);
    }
  }, [query]);

  useEffect(() => {
    const handlePopState = () => {
      setQueryState(queryFromSearch(window.location.search));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const start = data?.pagination.total
    ? (data.pagination.page - 1) * data.pagination.per_page + 1
    : 0;
  const end = data?.pagination.total
    ? Math.min(
        data.pagination.page * data.pagination.per_page,
        data.pagination.total,
      )
    : 0;

  return (
    <>
      <section className="page-header">
        <h1>Audit Log</h1>
      </section>
      {loading ? (
        <section className="card empty-state" role="status">
          Loading audit history…
        </section>
      ) : loadError ? (
        <section className="card empty-state" role="alert">
          <p>Audit history could not be loaded. Please try again.</p>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => void load()}
          >
            Try again
          </button>
        </section>
      ) : (
        <section className="card table-card">
          {data?.audit_logs.length ? (
            <>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>IP</th>
                      <th>User</th>
                      <th>Action</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.audit_logs.map((log, index) => (
                      <tr key={log.id ?? `${log.created_at}-${index}`}>
                        <td>{log.created_at}</td>
                        <td>{log.target_label}</td>
                        <td>{log.username || "System"}</td>
                        <td>
                          <AuditActionBadge action={log.action} />
                        </td>
                        <td>{log.changes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <footer className="table-footer">
                <p className="table-meta">
                  Showing {start}-{end} of {data.pagination.total}
                </p>
                <div className="table-footer-controls">
                  <label className="table-per-page field field-inline">
                    <span>Rows</span>
                    <select
                      className="select select-minimal"
                      aria-label="Rows per page"
                      value={queryState.per_page}
                      onChange={(event) =>
                        setQueryState({
                          page: 1,
                          per_page: Number(event.target.value),
                        })
                      }
                    >
                      {PAGE_SIZES.map((size) => (
                        <option key={size} value={size}>
                          {size}
                        </option>
                      ))}
                    </select>
                  </label>
                  <nav
                    className="pagination"
                    aria-label="Audit log pagination"
                  >
                    <button
                      className="btn btn-secondary btn-small"
                      type="button"
                      disabled={data.pagination.page <= 1}
                      onClick={() =>
                        setQueryState((current) => ({
                          ...current,
                          page: current.page - 1,
                        }))
                      }
                    >
                      Previous
                    </button>
                    <span className="pagination-status">
                      Page {data.pagination.page} of{" "}
                      {data.pagination.total_pages}
                    </span>
                    <button
                      className="btn btn-secondary btn-small"
                      type="button"
                      disabled={
                        data.pagination.page >= data.pagination.total_pages
                      }
                      onClick={() =>
                        setQueryState((current) => ({
                          ...current,
                          page: current.page + 1,
                        }))
                      }
                    >
                      Next
                    </button>
                  </nav>
                </div>
              </footer>
            </>
          ) : (
            <p>No audit history yet.</p>
          )}
        </section>
      )}
    </>
  );
}
