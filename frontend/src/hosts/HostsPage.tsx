import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  createHost,
  deleteHost,
  fetchHosts,
  updateHost,
} from "./api";
import { HostDrawer } from "./HostDrawer";
import { HostsFilters } from "./HostsFilters";
import { HostsTable } from "./HostsTable";
import type {
  HostFilters,
  HostFormValues,
  HostsBootstrap,
  HostRow,
  HostsResponse,
} from "./types";

const emptyValues: HostFormValues = {
  name: "",
  vendor_id: "",
  project_id: "",
  os_ips: "",
  bmc_ips: "",
  notes: "",
};

function filtersFromSearch(search: string): HostFilters {
  const params = new URLSearchParams(search);
  return {
    q: params.get("q") ?? "",
    project_id: params.get("project_id") ?? "",
    unassigned_only: params.get("unassigned-only") === "true",
    status: params.get("status") ?? "",
    vendor_id: params.get("vendor_id") ?? "",
    tags: params.getAll("tag"),
    page: Number(params.get("page") || 1),
    per_page: Number(params.get("per-page") || 20),
  };
}

function searchFromFilters(filters: HostFilters): string {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.project_id) params.set("project_id", filters.project_id);
  if (filters.unassigned_only) params.set("unassigned-only", "true");
  if (filters.status) params.set("status", filters.status);
  if (filters.vendor_id) params.set("vendor_id", filters.vendor_id);
  filters.tags.forEach((tag) => params.append("tag", tag));
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.per_page !== 20) params.set("per-page", String(filters.per_page));
  return params.toString();
}

function valuesForHost(host: HostRow, response: HostsResponse): HostFormValues {
  const vendor = response.filters.vendors.find(
    (item) => item.name === host.vendor,
  );
  return {
    name: host.name,
    vendor_id: vendor ? String(vendor.id) : "",
    project_id:
      host.project_count > 1
        ? "mixed"
        : host.project_id
          ? String(host.project_id)
          : "",
    os_ips: host.os_ip_links.map((item) => item.ip_address).join(", "),
    bmc_ips: host.bmc_ip_links.map((item) => item.ip_address).join(", "),
    notes: host.notes ?? "",
  };
}

export function HostsPage({
  endpoint,
  initialQuery = "",
  bootstrap = null,
}: {
  endpoint: string;
  initialQuery?: string;
  bootstrap?: HostsBootstrap | null;
}) {
  const [filters, setFilters] = useState(() =>
    filtersFromSearch(initialQuery || window.location.search),
  );
  const [debouncedQuery, setDebouncedQuery] = useState(filters.q);
  const [data, setData] = useState<HostsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mode, setMode] = useState<"create" | "edit" | "delete" | null>(null);
  const [activeHost, setActiveHost] = useState<HostRow | null>(null);
  const [values, setValues] = useState(emptyValues);
  const [initialValues, setInitialValues] = useState(emptyValues);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const requestId = useRef(0);
  const legacyDrawerApplied = useRef(false);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(filters.q), 400);
    return () => window.clearTimeout(timeout);
  }, [filters.q]);

  const query = useMemo(
    () => searchFromFilters({ ...filters, q: debouncedQuery }),
    [debouncedQuery, filters],
  );

  const load = useCallback(
    async (showLoading = true) => {
      const id = ++requestId.current;
      const controller = new AbortController();
      if (showLoading) setLoading(true);
      setLoadError(null);
      try {
        const response = await fetchHosts(
          `${endpoint}${query ? `?${query}` : ""}`,
          controller.signal,
        );
        if (id === requestId.current) setData(response);
      } catch (error) {
        if (id === requestId.current && !(error instanceof DOMException)) {
          setLoadError("Hosts could not be loaded. Please try again.");
        }
      } finally {
        if (id === requestId.current && showLoading) setLoading(false);
      }
      return () => controller.abort();
    },
    [endpoint, query],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!data || legacyDrawerApplied.current) return;
    const params = new URLSearchParams(initialQuery || window.location.search);
    const deleteId = Number(params.get("delete"));
    const editId = Number(params.get("edit"));
    const target =
      bootstrap?.host ??
      data.hosts.find((host) => host.id === (deleteId || editId));
    if (target && deleteId) openDelete(target);
    if (target && editId) openEdit(target);
    legacyDrawerApplied.current = true;
  }, [bootstrap, data, initialQuery]);

  useEffect(() => {
    const initialParams = new URLSearchParams(
      initialQuery || window.location.search,
    );
    if (
      (initialParams.has("edit") || initialParams.has("delete")) &&
      !legacyDrawerApplied.current
    ) {
      return;
    }
    const next = query ? `/ui/hosts?${query}` : "/ui/hosts";
    if (`${window.location.pathname}${window.location.search}` !== next) {
      window.history.pushState({}, "", next);
    }
  }, [query]);

  useEffect(() => {
    const pop = () => {
      const next = filtersFromSearch(window.location.search);
      setFilters(next);
      setDebouncedQuery(next.q);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);

  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  const paginationStart = data?.pagination.total
    ? (data.pagination.page - 1) * data.pagination.per_page + 1
    : 0;
  const paginationEnd = data?.pagination.total
    ? Math.min(
        data.pagination.page * data.pagination.per_page,
        data.pagination.total,
      )
    : 0;
  const closeDrawer = useCallback(() => {
    if ((mode === "create" || mode === "edit") && dirty) {
      if (!window.confirm("Discard changes?")) return;
    }
    setMode(null);
    setErrors([]);
  }, [dirty, mode]);

  function patchFilters(patch: Partial<HostFilters>) {
    setFilters((current) => ({ ...current, ...patch, page: 1 }));
  }

  function openCreate() {
    setMode("create");
    setActiveHost(null);
    setValues(emptyValues);
    setInitialValues(emptyValues);
    setErrors([]);
  }

  function openEdit(host: HostRow) {
    if (!data) return;
    const next = valuesForHost(host, data);
    setMode("edit");
    setActiveHost(host);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
  }

  function openDelete(host: HostRow) {
    setMode("delete");
    setActiveHost(host);
    setAcknowledged(false);
    setConfirmName("");
    setErrors([]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mode || saving) return;
    setSaving(true);
    setErrors([]);
    try {
      if (mode === "create") await createHost(endpoint, values);
      if (mode === "edit" && activeHost)
        await updateHost(endpoint, activeHost.id, values);
      if (mode === "delete" && activeHost)
        await deleteHost(endpoint, activeHost.id, confirmName);
      setMode(null);
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof ApiError
          ? error.messages
          : ["Host request could not be completed."],
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">Inventory</p>
          <h1>Hosts</h1>
          <p className="subtitle">
            Track physical hosts and linked OS/BMC addresses.
          </p>
        </div>
        {data?.can_edit && (
          <div className="page-header-actions">
            <button className="btn btn-primary" type="button" onClick={openCreate}>
              New Host
            </button>
          </div>
        )}
      </section>
      <HostsFilters
        filters={filters}
        projects={data?.filters.projects ?? []}
        vendors={data?.filters.vendors ?? []}
        tags={data?.filters.tags ?? []}
        onChange={patchFilters}
      />
      {loading ? (
        <section className="card empty-state" role="status">
          Loading hosts…
        </section>
      ) : loadError ? (
        <section className="card empty-state" role="alert">
          <p>{loadError}</p>
          <button className="btn btn-secondary" type="button" onClick={() => void load()}>
            Try again
          </button>
        </section>
      ) : (
        <>
          <HostsTable
            hosts={data?.hosts ?? []}
            canEdit={data?.can_edit ?? false}
            onEdit={openEdit}
            onDelete={openDelete}
            onTag={(tag) =>
              patchFilters({
                tags: filters.tags.includes(tag)
                  ? filters.tags
                  : [...filters.tags, tag],
              })
            }
            footer={
              data && data.pagination.total > 0 ? (
                <footer className="table-footer hosts-table-footer">
                  <p className="table-meta hosts-table-summary">
                    Showing <strong>{paginationStart}–{paginationEnd}</strong> of{" "}
                    <strong>{data.pagination.total}</strong>
                  </p>
                  <div className="table-footer-controls hosts-pagination-controls">
                    <label className="hosts-rows-control">
                      <span>Rows per page</span>
                      <select
                        className="select select-minimal"
                        aria-label="Rows per page"
                        value={filters.per_page}
                        onChange={(event) =>
                          patchFilters({ per_page: Number(event.target.value) })
                        }
                      >
                        {[10, 20, 50, 100].map((size) => (
                          <option key={size} value={size}>
                            {size}
                          </option>
                        ))}
                      </select>
                    </label>
                    <nav
                      className="pagination hosts-pagination"
                      aria-label="Hosts pagination"
                    >
                      <button
                        className="btn btn-secondary btn-small"
                        type="button"
                        disabled={data.pagination.page <= 1}
                        onClick={() =>
                          setFilters((current) => ({
                            ...current,
                            page: current.page - 1,
                          }))
                        }
                      >
                        Previous
                      </button>
                      <span className="pagination-status">
                        {data.pagination.page} / {data.pagination.total_pages}
                      </span>
                      <button
                        className="btn btn-secondary btn-small"
                        type="button"
                        disabled={
                          data.pagination.page >= data.pagination.total_pages
                        }
                        onClick={() =>
                          setFilters((current) => ({
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
              ) : undefined
            }
          />
        </>
      )}
      <HostDrawer
        mode={mode}
        host={activeHost}
        values={values}
        projects={data?.filters.projects ?? []}
        vendors={data?.filters.vendors ?? []}
        errors={errors}
        dirty={dirty}
        saving={saving}
        acknowledged={acknowledged}
        confirmName={confirmName}
        onValue={(field, value) => {
          setValues((current) => ({ ...current, [field]: value }));
          setErrors([]);
        }}
        onAcknowledged={setAcknowledged}
        onConfirmName={setConfirmName}
        onClose={closeDrawer}
        onSubmit={submit}
      />
    </>
  );
}
