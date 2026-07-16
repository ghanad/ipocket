import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { tagColorStyle } from "../shared/tagColor";
import {
  createRangeAddress,
  fetchRangeAddresses,
  RangeAddressesApiError,
  updateRangeAddress,
} from "./api";
import { RangeAddressDrawer } from "./RangeAddressDrawer";
import type {
  AddressFormValues,
  RangeAddressFilters,
  RangeAddressRow,
  RangeAddressesResponse,
} from "./types";

function RangeTagOverflowPopover({
  row,
  anchor,
  onClose,
  onSelect,
}: {
  row: RangeAddressRow;
  anchor: HTMLElement;
  onClose: () => void;
  onSelect: (tag: string) => void;
}) {
  const [search, setSearch] = useState("");
  const rect = anchor.getBoundingClientRect();
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);
  const visible = row.tags.filter((tag) =>
    tag.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <div
      className="ip-tags-popover"
      role="dialog"
      aria-label={`Tags for ${row.ip_address}`}
      style={{ position: "fixed", top: rect.bottom + 6, left: rect.left }}
    >
      <div className="ip-tags-popover-header">
        <h3 className="ip-tags-popover-title">Tags</h3>
        <button className="ip-tags-popover-close" type="button" aria-label="Close tags" onClick={onClose}>✕</button>
      </div>
      <label className="field ip-tags-popover-search-field">
        <span className="visually-hidden">Filter tags</span>
        <input className="input" aria-label="Filter tags" value={search} onChange={(event) => setSearch(event.target.value)} />
      </label>
      <div className="ip-tags-popover-list">
        {visible.map((tag) => (
          <button key={tag.name} className="tag tag-color tag-filter-chip" style={tagColorStyle(tag.color)} type="button" onClick={() => onSelect(tag.name)}>{tag.name}</button>
        ))}
        {!visible.length && <p className="muted">No matching tags.</p>}
      </div>
    </div>
  );
}

const defaultFilters: RangeAddressFilters = {
  q: "",
  project_id: "",
  type: "",
  tags: [],
  status: "all",
  page: 1,
  per_page: 20,
};
const emptyValues: AddressFormValues = {
  ip_address: "",
  type: "VM",
  project_id: "",
  tags: [],
  notes: "",
};

export function filtersFromSearch(search: string, hash = ""): RangeAddressFilters {
  const params = new URLSearchParams(search);
  const rawStatus = params.get("status");
  const hashStatus = hash === "#used" ? "used" : hash === "#free" ? "free" : null;
  const status = ["all", "used", "free"].includes(rawStatus ?? "")
    ? rawStatus!
    : !rawStatus && hashStatus
      ? hashStatus
      : "all";
  const perPage = Number(params.get("per-page") || 20);
  return {
    q: params.get("q") ?? "",
    project_id: params.get("project_id") ?? "",
    type: params.get("type") ?? "",
    tags: params.getAll("tag"),
    status: status as RangeAddressFilters["status"],
    page: Math.max(1, Number(params.get("page") || 1) || 1),
    per_page: [10, 20, 50, 100].includes(perPage) ? perPage : 20,
  };
}

export function searchFromFilters(filters: RangeAddressFilters): string {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.project_id) params.set("project_id", filters.project_id);
  if (filters.type) params.set("type", filters.type);
  filters.tags.forEach((tag) => params.append("tag", tag));
  if (filters.status !== "all") params.set("status", filters.status);
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.per_page !== 20) params.set("per-page", String(filters.per_page));
  return params.toString();
}

function valuesForRow(row: RangeAddressRow): AddressFormValues {
  return {
    ip_address: row.ip_address,
    type: row.asset_type ?? "VM",
    project_id: String(row.project_id ?? ""),
    tags: row.tags.map((tag) => tag.name),
    notes: row.notes,
  };
}

function anchorForIp(ip: string) {
  return `ip-${ip.replace(/[.:]/g, "-")}`;
}

export function RangeAddressesPage({
  endpoint,
  initialQuery = "",
}: {
  endpoint: string;
  initialQuery?: string;
}) {
  const [filters, setFilters] = useState(() =>
    filtersFromSearch(
      initialQuery ? `?${initialQuery}` : window.location.search,
      window.location.hash,
    ),
  );
  const [debouncedQuery, setDebouncedQuery] = useState(filters.q);
  const [data, setData] = useState<RangeAddressesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [popover, setPopover] = useState<{ row: RangeAddressRow; anchor: HTMLElement } | null>(null);
  const [mode, setMode] = useState<"add" | "edit" | null>(null);
  const [activeRow, setActiveRow] = useState<RangeAddressRow | null>(null);
  const [values, setValues] = useState(emptyValues);
  const [initialValues, setInitialValues] = useState(emptyValues);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [focusIp, setFocusIp] = useState<string | null>(null);
  const requestId = useRef(0);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(filters.q), 500);
    return () => window.clearTimeout(timeout);
  }, [filters.q]);
  const query = useMemo(
    () => searchFromFilters({ ...filters, q: debouncedQuery }),
    [debouncedQuery, filters],
  );
  const load = useCallback(async (showLoading = true) => {
    const id = ++requestId.current;
    controller.current?.abort();
    const nextController = new AbortController();
    controller.current = nextController;
    if (showLoading) setLoading(true);
    setLoadError(null);
    try {
      const response = await fetchRangeAddresses(
        `${endpoint}${query ? `?${query}` : ""}`,
        nextController.signal,
      );
      if (id !== requestId.current) return;
      setData(response);
      setFilters((current) => ({
        ...current,
        project_id: response.query.project_id,
        type: response.query.type,
        tags: response.query.tags,
        status: response.query.status,
        page: response.query.page,
        per_page: response.query.per_page,
      }));
    } catch (error) {
      if (
        id === requestId.current &&
        !(error instanceof DOMException && error.name === "AbortError")
      ) {
        setLoadError("Range addresses could not be loaded. Please try again.");
      }
    } finally {
      if (id === requestId.current && showLoading) setLoading(false);
    }
  }, [endpoint, query]);
  useEffect(() => {
    void load();
    return () => controller.current?.abort();
  }, [load]);
  useEffect(() => {
    const next = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== next) {
      window.history.pushState({}, "", next);
    }
  }, [query]);
  useEffect(() => {
    const pop = () => {
      const next = filtersFromSearch(window.location.search, window.location.hash);
      setFilters(next);
      setDebouncedQuery(next.q);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => {
    if (!focusIp || loading) return;
    const row = document.getElementById(anchorForIp(focusIp));
    if (row) {
      row.scrollIntoView({ block: "center" });
      row.focus();
      window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}#${anchorForIp(focusIp)}`);
      setFocusIp(null);
    }
  }, [data, focusIp, loading]);
  useEffect(() => {
    if (loading || !data || !window.location.hash.startsWith("#ip-")) return;
    const row = document.getElementById(window.location.hash.slice(1));
    row?.scrollIntoView({ block: "center" });
  }, [data, loading]);

  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  const closeDrawer = useCallback(() => {
    if (dirty && !window.confirm("Discard changes?")) return;
    setMode(null);
    setErrors([]);
  }, [dirty]);
  function patchFilters(patch: Partial<RangeAddressFilters>) {
    setFilters((current) => ({ ...current, ...patch, page: 1 }));
  }
  function addTag(raw: string) {
    const name = raw.trim().toLowerCase();
    if (!name || !data?.filters.tags.some((tag) => tag.name === name) || filters.tags.includes(name)) return;
    patchFilters({ tags: [...filters.tags, name] });
    setTagInput("");
  }
  function submitTag(event: FormEvent) {
    event.preventDefault();
    addTag(tagInput);
  }
  function openAdd(row: RangeAddressRow) {
    if (!row.policy.can_add) return;
    const next = { ...emptyValues, ip_address: row.ip_address };
    setActiveRow(row);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setMode("add");
  }
  function openEdit(row: RangeAddressRow) {
    if (!row.policy.can_edit) return;
    const next = valuesForRow(row);
    setActiveRow(row);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setMode("edit");
  }
  async function submit() {
    if (!mode || !activeRow || saving || !dirty) return;
    setSaving(true);
    setErrors([]);
    try {
      if (mode === "add") await createRangeAddress(endpoint, values);
      else if (activeRow.asset_id) await updateRangeAddress(endpoint, activeRow.asset_id, values);
      const ip = values.ip_address;
      setToast(mode === "add" ? "IP asset created." : "IP asset updated.");
      setMode(null);
      setFocusIp(ip);
      if (mode === "add" && filters.status === "free") {
        setFilters((current) => ({ ...current, status: "all", page: 1 }));
      } else {
        await load(false);
      }
    } catch (error) {
      setErrors(
        error instanceof RangeAddressesApiError
          ? error.messages
          : ["Range address request could not be completed."],
      );
    } finally {
      setSaving(false);
    }
  }

  const catalog = new Map(data?.filters.tags.map((tag) => [tag.name, tag]) ?? []);
  return (
    <>
      {toast && (
        <div className="toast-container" role="status">
          <div className="toast toast-success">
            <span className="toast-message">{toast}</span>
            <button className="toast-close" type="button" aria-label="Dismiss notification" onClick={() => setToast(null)}>×</button>
          </div>
        </div>
      )}
      <section className="page-header">
        <div>
          <h1>{data?.range.name ?? "Range addresses"}</h1>
          <p className="subtitle">
            {data ? `CIDR ${data.range.cidr} • ${data.range.used} used • ${data.range.free} free` : "Loading range details…"}
          </p>
        </div>
        <div className="page-actions">
          <a className="btn btn-secondary" href="/ui/ranges">Back to ranges</a>
        </div>
      </section>
      <section className="card">
        <div className="card-header">
          <div>
            <h2>Range details</h2>
            <p className="subtitle">
              Usable total: {data?.range.total_usable ?? "—"} (excludes network/broadcast for /30 and larger ranges).
            </p>
          </div>
        </div>
        <div className="card-body">
          <p className="muted">Click the Used or Free counts on the utilization tables to return here.</p>
        </div>
      </section>
      <section className="card filter-card">
        <div className="filters-grid">
          <label className="field">
            <span>IP address</span>
            <input className="input" type="search" placeholder="Search IP" value={filters.q} onChange={(event) => patchFilters({ q: event.target.value })} />
          </label>
          <label className="field">
            <span>Project</span>
            <select className="select" aria-label="Project" value={filters.project_id} onChange={(event) => patchFilters({ project_id: event.target.value })}>
              <option value="">All</option>
              <option value="unassigned">Unassigned</option>
              {data?.filters.projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Type</span>
            <select className="select" aria-label="Type filter" value={filters.type} onChange={(event) => patchFilters({ type: event.target.value })}>
              <option value="">All</option>
              {data?.filters.types.map((type) => <option key={type}>{type}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Status</span>
            <select className="select" aria-label="Status" value={filters.status} onChange={(event) => patchFilters({ status: event.target.value as RangeAddressFilters["status"] })}>
              <option value="all">All</option>
              <option value="used">Used</option>
              <option value="free">Free</option>
            </select>
          </label>
          <div className="field field-tag-filter">
            <span>Tags</span>
            <form className="tag-filter-controls" onSubmit={submitTag}>
              <input className="input" aria-label="Tag filter" placeholder="Type tag and press Enter" list="range-address-tag-suggestions" value={tagInput} onChange={(event) => setTagInput(event.target.value)} />
            </form>
            <datalist id="range-address-tag-suggestions">
              {data?.filters.tags.map((tag) => <option key={tag.id} value={tag.name} />)}
            </datalist>
            <div className="tag-filter-selected">
              {filters.tags.map((name) => (
                <span className="tag-filter-entry" key={name}>
                  <button className="tag tag-color tag-filter-chip" style={tagColorStyle(catalog.get(name)?.color ?? "#e2e8f0")} type="button" onClick={() => patchFilters({ tags: filters.tags.filter((tag) => tag !== name) })}>{name} ×</button>
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>
      {loading ? (
        <section className="card empty-state" role="status">Loading range addresses…</section>
      ) : loadError ? (
        <section className="card empty-state" role="alert">
          <p>{loadError}</p>
          <button className="btn btn-secondary" type="button" onClick={() => void load()}>Try again</button>
        </section>
      ) : (
        <section className="card table-card" id="addresses">
          <div className="card-header card-header-padded">
            <div>
              <h2>Addresses in this range</h2>
              <p className="subtitle">Used: {data?.range.used ?? 0} • Free: {data?.range.free ?? 0}</p>
            </div>
          </div>
          <div className="table-wrapper">
            <table className="table table-range-addresses">
              <thead><tr><th>IP address</th><th>Status</th><th>Project</th><th>Type</th><th>Host Pair</th><th>Tags</th><th>Notes</th><th>Action</th></tr></thead>
              <tbody>
                {!data?.addresses.length ? (
                  <tr><td colSpan={8} className="empty-state">No addresses in this range.</td></tr>
                ) : data.addresses.map((row) => (
                  <tr key={row.ip_address} id={anchorForIp(row.ip_address)} tabIndex={-1}>
                    <td className="mono">{row.asset_id ? <a className="link" href={`/ui/ip-assets/${row.asset_id}`}>{row.ip_address}</a> : row.ip_address}</td>
                    <td><span className={`pill ${row.status === "used" ? "pill-danger" : "pill-success"}`}>{row.status === "used" ? "Used" : "Free"}</span></td>
                    <td>{row.status === "free" ? <span className="muted">—</span> : row.project_unassigned ? <span className="tag tag-warning">Unassigned</span> : <span className="tag tag-project" style={{ "--project-color": row.project_color } as React.CSSProperties}>{row.project_name}</span>}</td>
                    <td className="muted">{row.asset_type ?? "—"}</td>
                    <td>{row.host_pair ? <span className="mono">{row.host_pair}</span> : <span className="muted">—</span>}</td>
                    <td className="ip-tags-cell">
                      {row.tags.length ? <div className="ip-tags-inline" aria-label={`Tags for ${row.ip_address}`}>
                        {row.tags.slice(0, 3).map((tag) => <button key={tag.name} className="tag tag-color tag-filter-chip" style={tagColorStyle(tag.color)} type="button" onClick={() => addTag(tag.name)}>{tag.name}</button>)}
                        {row.tags.length > 3 && <button className="tag tag-muted ip-tags-more" type="button" aria-haspopup="dialog" aria-expanded={popover?.row.ip_address === row.ip_address} onMouseEnter={(event) => setPopover({ row, anchor: event.currentTarget })} onFocus={(event) => setPopover({ row, anchor: event.currentTarget })} onClick={(event) => setPopover({ row, anchor: event.currentTarget })}>+{row.tags.length - 3} more</button>}
                      </div> : <span className="muted">—</span>}
                    </td>
                    <td className="muted ip-note-cell">{row.notes || "—"}</td>
                    <td>{row.policy.can_add ? <button className="btn btn-secondary btn-small" type="button" onClick={() => openAdd(row)}>Add…</button> : row.policy.can_edit ? <button className="btn btn-secondary btn-small" type="button" onClick={() => openEdit(row)}>Edit</button> : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <footer className="table-footer">
            <p className="table-meta">{data?.pagination.total ? `Showing ${data.pagination.start_index}-${data.pagination.end_index} of ${data.pagination.total}` : "No results to display."}</p>
            <div className="table-footer-controls">
              <label className="table-per-page field field-inline">
                <span>Rows</span>
                <select className="select select-minimal" aria-label="Rows per page" value={filters.per_page} onChange={(event) => patchFilters({ per_page: Number(event.target.value) })}>
                  {[10, 20, 50, 100].map((size) => <option key={size}>{size}</option>)}
                </select>
              </label>
              <nav className="pagination" aria-label="Range addresses pagination">
                <button className="btn btn-secondary btn-small" type="button" disabled={!data?.pagination.has_prev} onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}>Previous</button>
                <span className="pagination-status">Page {data?.pagination.page ?? 1} of {data?.pagination.total_pages ?? 1}</span>
                <button className="btn btn-secondary btn-small" type="button" disabled={!data?.pagination.has_next} onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}>Next</button>
              </nav>
            </div>
          </footer>
        </section>
      )}
      {popover && (
        <RangeTagOverflowPopover
          row={popover.row}
          anchor={popover.anchor}
          onClose={() => setPopover(null)}
          onSelect={(tag) => { addTag(tag); setPopover(null); }}
        />
      )}
      <RangeAddressDrawer
        mode={mode}
        values={values}
        initialValues={initialValues}
        projects={data?.filters.projects ?? []}
        tags={data?.filters.tags ?? []}
        types={data?.filters.types ?? ["OS", "BMC", "VM", "VIP", "OTHER"]}
        errors={errors}
        saving={saving}
        onValues={(next) => { setValues(next); setErrors([]); }}
        onClose={closeDrawer}
        onSubmit={() => void submit()}
      />
    </>
  );
}
