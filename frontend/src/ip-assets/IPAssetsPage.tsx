import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  autoHostAsset,
  bulkUpdateAssets,
  createAsset,
  deleteAsset,
  fetchAssets,
  IPAssetsApiError,
  updateAsset,
} from "./api";
import { BulkUpdateDrawer } from "./BulkUpdateDrawer";
import { IPAssetListDrawer } from "./IPAssetListDrawer";
import { IPAssetsFilters } from "./IPAssetsFilters";
import { IPAssetsTable } from "./IPAssetsTable";
import type {
  AssetFilters,
  AssetFormValues,
  AssetRow,
  AssetsResponse,
  BulkValues,
} from "./types";

const emptyAsset: AssetFormValues = {
  ip_address: "",
  type: "VM",
  project_id: "",
  host_id: "",
  tags: [],
  notes: "",
};
const emptyBulk: BulkValues = {
  type: "",
  projectMode: "",
  project_id: "",
  tags_to_add: [],
  tags_to_remove: [],
  notes_mode: "",
  notes: "",
};

export function filtersFromSearch(search: string): AssetFilters {
  const params = new URLSearchParams(search);
  const perPage = Number(params.get("per-page") || 20);
  const unassignedOnly = params.get("unassigned-only") === "true";
  return {
    q: params.get("q") ?? "",
    project_id: params.get("project_id") ?? "",
    type: params.get("type") ?? "",
    assigned_only:
      params.get("assigned-only") === "true" && !unassignedOnly,
    unassigned_only: unassignedOnly,
    archived_only: params.get("archived-only") === "true",
    tag_any: [...params.getAll("tag"), ...params.getAll("tag_any")].filter(
      (value, index, values) => values.indexOf(value) === index,
    ),
    tag_all: params.getAll("tag_all"),
    tag_not: params.getAll("tag_not"),
    page: Math.max(1, Number(params.get("page") || 1) || 1),
    per_page: [10, 20, 50, 100].includes(perPage) ? perPage : 20,
  };
}

export function searchFromFilters(filters: AssetFilters): string {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.project_id) params.set("project_id", filters.project_id);
  if (filters.type) params.set("type", filters.type);
  if (filters.unassigned_only) {
    params.set("unassigned-only", "true");
  } else if (filters.assigned_only) {
    params.set("assigned-only", "true");
  }
  if (filters.archived_only) params.set("archived-only", "true");
  filters.tag_any.forEach((tag) => params.append("tag_any", tag));
  filters.tag_all.forEach((tag) => params.append("tag_all", tag));
  filters.tag_not.forEach((tag) => params.append("tag_not", tag));
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.per_page !== 20) params.set("per-page", String(filters.per_page));
  return params.toString();
}

function valuesForAsset(asset: AssetRow): AssetFormValues {
  return {
    ip_address: asset.ip_address,
    type: asset.type,
    project_id: String(asset.project_id || ""),
    host_id: String(asset.host_id || ""),
    tags: asset.tags.map((tag) => tag.name),
    notes: asset.notes,
  };
}

export function IPAssetsPage({
  endpoint,
  initialQuery = "",
}: {
  endpoint: string;
  initialQuery?: string;
}) {
  const [filters, setFilters] = useState(() =>
    filtersFromSearch(initialQuery || window.location.search),
  );
  const [debouncedQuery, setDebouncedQuery] = useState(filters.q);
  const [data, setData] = useState<AssetsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [mode, setMode] = useState<"create" | "edit" | "delete" | null>(null);
  const [asset, setAsset] = useState<AssetRow | null>(null);
  const [values, setValues] = useState(emptyAsset);
  const [initialValues, setInitialValues] = useState(emptyAsset);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkValues, setBulkValues] = useState(emptyBulk);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(filters.q), 500);
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
        const response = await fetchAssets(
          `${endpoint}${query ? `?${query}` : ""}`,
          controller.signal,
        );
        if (id === requestId.current) {
          setData(response);
          if (response.pagination.page !== filters.page) {
            setFilters((current) => ({
              ...current,
              page: response.pagination.page,
            }));
          }
        }
      } catch (error) {
        if (
          id === requestId.current &&
          !(error instanceof DOMException && error.name === "AbortError")
        ) {
          setLoadError("IP assets could not be loaded. Please try again.");
        }
      } finally {
        if (id === requestId.current && showLoading) setLoading(false);
      }
      return () => controller.abort();
    },
    [endpoint, filters.page, query],
  );
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    const next = query ? `/ui/ip-assets?${query}` : "/ui/ip-assets";
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
  const commonTags = useMemo(() => {
    const selectedRows =
      data?.assets.filter((row) => selected.has(row.id)) ?? [];
    if (!selectedRows.length) return [];
    return selectedRows
      .map((row) => row.tags.map((tag) => tag.name))
      .reduce((common, tags) => common.filter((tag) => tags.includes(tag)));
  }, [data, selected]);
  const start = data?.pagination.total
    ? (data.pagination.page - 1) * data.pagination.per_page + 1
    : 0;
  const end = data?.pagination.total
    ? Math.min(
        data.pagination.page * data.pagination.per_page,
        data.pagination.total,
      )
    : 0;

  function patchFilters(patch: Partial<AssetFilters>) {
    setFilters((current) => ({ ...current, ...patch, page: 1 }));
    setSelected(new Set());
  }
  function quickFilter(name: string, value: string) {
    if (name === "tag_any") {
      patchFilters({
        tag_any: filters.tag_any.includes(value)
          ? filters.tag_any
          : [...filters.tag_any, value],
      });
      return;
    }
    patchFilters({ [name]: value });
  }
  const closeDrawer = useCallback(() => {
    if ((mode === "create" || mode === "edit") && dirty) {
      if (!window.confirm("Discard changes?")) return;
    }
    setMode(null);
    setErrors([]);
  }, [dirty, mode]);
  function openCreate() {
    setAsset(null);
    setValues(emptyAsset);
    setInitialValues(emptyAsset);
    setErrors([]);
    setMode("create");
  }
  function openEdit(row: AssetRow) {
    const next = valuesForAsset(row);
    setAsset(row);
    setValues(next);
    setInitialValues(next);
    setErrors([]);
    setMode("edit");
  }
  function openDelete(row: AssetRow) {
    setAsset(row);
    setValues(valuesForAsset(row));
    setInitialValues(valuesForAsset(row));
    setErrors([]);
    setMode("delete");
  }
  async function submit(acknowledged: boolean, confirmIp: string) {
    if (!mode || saving) return;
    setSaving(true);
    setErrors([]);
    try {
      if (mode === "create") await createAsset(endpoint, values);
      if (mode === "edit" && asset)
        await updateAsset(endpoint, asset.id, values);
      if (mode === "delete" && asset)
        await deleteAsset(endpoint, asset.id, acknowledged, confirmIp);
      setToast(
        mode === "create"
          ? "IP asset created."
          : mode === "delete"
            ? "IP asset deleted."
            : "IP asset updated.",
      );
      setMode(null);
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof IPAssetsApiError
          ? error.messages
          : ["IP asset request could not be completed."],
      );
    } finally {
      setSaving(false);
    }
  }
  async function autoHost() {
    if (!asset) return;
    setSaving(true);
    setErrors([]);
    try {
      const host = await autoHostAsset(endpoint, asset.id);
      const next = { ...values, host_id: String(host.host_id) };
      setValues(next);
      setInitialValues(next);
      setToast(`Created and assigned ${host.host_name}.`);
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof IPAssetsApiError
          ? error.messages
          : ["Host could not be created."],
      );
    } finally {
      setSaving(false);
    }
  }
  async function submitBulk(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setErrors([]);
    try {
      const result = await bulkUpdateAssets(
        endpoint,
        [...selected],
        bulkValues,
      );
      setToast(`Updated ${result.updated_count} IP assets.`);
      setSelected(new Set());
      setBulkOpen(false);
      setBulkValues(emptyBulk);
      await load(false);
    } catch (error) {
      setErrors(
        error instanceof IPAssetsApiError
          ? error.messages
          : ["Bulk update could not be completed."],
      );
    } finally {
      setSaving(false);
    }
  }

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
          <p className="eyebrow">Inventory</p>
          <h1>IP Assets</h1>
          <p className="subtitle">Manage and monitor network address assignments across all zones.</p>
        </div>
        {data?.can_edit && (
          <div className="page-header-actions">
            <button className="btn btn-primary" type="button" onClick={openCreate}>Add IP</button>
          </div>
        )}
      </section>
      <IPAssetsFilters
        filters={filters}
        projects={data?.filters.projects ?? []}
        tags={data?.filters.tags ?? []}
        types={data?.filters.types ?? []}
        onChange={patchFilters}
      />
      {data?.can_edit && selected.size > 0 && (
        <div className="bulk-action-bar">
          <span>{selected.size} selected</span>
          <button className="btn btn-primary btn-small" type="button" onClick={() => { setErrors([]); setBulkOpen(true); }}>Bulk update</button>
        </div>
      )}
      {loading ? (
        <section className="card empty-state" role="status">Loading IP assets…</section>
      ) : loadError ? (
        <section className="card empty-state" role="alert">
          <p>{loadError}</p>
          <button className="btn btn-secondary" type="button" onClick={() => void load()}>Try again</button>
        </section>
      ) : (
        <IPAssetsTable
          assets={data?.assets ?? []}
          canEdit={data?.can_edit ?? false}
          selected={selected}
          onSelected={setSelected}
          onQuickFilter={quickFilter}
          onEdit={openEdit}
          onDelete={openDelete}
          footer={
            data ? (
              <footer className="table-footer">
                <p className="table-meta">
                  {data.pagination.total
                    ? <>Showing {start}-{end} of {data.pagination.total}</>
                    : "No results to display."}
                </p>
                <div className="table-footer-controls">
                  <label className="table-per-page field field-inline">
                    <span>Rows</span>
                    <select
                      className="select select-minimal"
                      aria-label="Rows per page"
                      value={filters.per_page}
                      onChange={(event) => patchFilters({ per_page: Number(event.target.value) })}
                    >
                      {[10, 20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
                    </select>
                  </label>
                  <nav className="pagination" aria-label="IP assets pagination">
                    <button className="btn btn-secondary btn-small" type="button" disabled={data.pagination.page <= 1} onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}>Previous</button>
                    <span className="pagination-status">Page {data.pagination.page} of {data.pagination.total_pages}</span>
                    <button className="btn btn-secondary btn-small" type="button" disabled={data.pagination.page >= data.pagination.total_pages} onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}>Next</button>
                  </nav>
                </div>
              </footer>
            ) : undefined
          }
        />
      )}
      <IPAssetListDrawer
        mode={mode}
        asset={asset}
        values={values}
        types={data?.filters.types ?? ["OS", "BMC", "VM", "VIP", "OTHER"]}
        projects={data?.filters.projects ?? []}
        hosts={data?.filters.hosts ?? []}
        tags={data?.filters.tags ?? []}
        errors={errors}
        saving={saving}
        dirty={dirty}
        onValues={(next) => { setValues(next); setErrors([]); }}
        onClose={closeDrawer}
        onSubmit={(acknowledged, confirmIp) => void submit(acknowledged, confirmIp)}
        onAutoHost={() => void autoHost()}
      />
      <BulkUpdateDrawer
        open={bulkOpen}
        selectedCount={selected.size}
        commonTags={commonTags}
        values={bulkValues}
        projects={data?.filters.projects ?? []}
        tags={data?.filters.tags ?? []}
        types={data?.filters.types ?? []}
        errors={errors}
        saving={saving}
        onValues={(next) => { setBulkValues(next); setErrors([]); }}
        onClose={() => { setBulkOpen(false); setErrors([]); }}
        onSubmit={(event) => void submitBulk(event)}
      />
    </>
  );
}
