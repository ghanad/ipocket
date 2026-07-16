import { useCallback, useEffect, useMemo, useState } from "react";

import { tagColorStyle } from "../shared/tagColor";
import { AuditLogTable } from "./AuditLogTable";
import {
  autoHostIPAsset,
  deleteIPAsset,
  fetchIPAssetDetail,
  IPAssetApiError,
  updateIPAsset,
} from "./api";
import { IPAssetDrawer } from "./IPAssetDrawer";
import type { DetailResponse, EditValues } from "./types";

function valuesFrom(data: DetailResponse): EditValues {
  return {
    type: data.asset.type,
    project_id: String(data.asset.project_id || ""),
    host_id: String(data.asset.host_id || ""),
    tags: data.asset.tags.map((tag) => tag.name),
    notes: data.asset.notes || "",
  };
}

export function IPAssetDetailPage({ endpoint }: { endpoint: string }) {
  const [data, setData] = useState<DetailResponse | null>(null);
  const [values, setValues] = useState<EditValues | null>(null);
  const [mode, setMode] = useState<"edit" | "delete" | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<IPAssetApiError | null>(null);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchIPAssetDetail(endpoint, signal);
      setData(result);
      setValues(valuesFrom(result));
    } catch (error) {
      if (!(error instanceof DOMException)) {
        setLoadError(
          error instanceof IPAssetApiError
            ? error
            : new IPAssetApiError(["IP asset details could not be loaded."]),
        );
      }
    } finally {
      setLoading(false);
    }
  }, [endpoint]);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);
  const dirty = useMemo(
    () =>
      Boolean(
        data &&
          values &&
          JSON.stringify(values) !== JSON.stringify(valuesFrom(data)),
      ),
    [data, values],
  );
  const close = useCallback(() => {
    if (mode === "edit" && dirty && !window.confirm("Discard changes?")) return;
    if (data) setValues(valuesFrom(data));
    setErrors([]);
    setMode(null);
  }, [data, dirty, mode]);
  const submit = async (acknowledged: boolean, confirmIp: string) => {
    if (!data || !values || !mode) return;
    setSaving(true);
    setErrors([]);
    try {
      if (mode === "delete") {
        await deleteIPAsset(endpoint, acknowledged, confirmIp);
        window.location.assign("/ui/ip-assets");
        return;
      }
      await updateIPAsset(endpoint, values);
      setMode(null);
      await load();
    } catch (error) {
      setErrors(
        error instanceof IPAssetApiError
          ? error.messages
          : ["IP asset request failed."],
      );
    } finally {
      setSaving(false);
    }
  };
  const autoHost = async () => {
    setSaving(true);
    setErrors([]);
    try {
      await autoHostIPAsset(endpoint);
      setMode(null);
      await load();
    } catch (error) {
      setErrors(
        error instanceof IPAssetApiError
          ? error.messages
          : ["Unable to create host."],
      );
    } finally {
      setSaving(false);
    }
  };
  if (loading) return <section className="card empty-state" role="status">Loading IP asset details…</section>;
  if (loadError?.status === 404) {
    return <section className="card empty-state" role="alert"><h1>IP asset not found</h1><a className="btn btn-secondary" href="/ui/ip-assets">Back to IP assets</a></section>;
  }
  if (loadError || !data || !values) {
    return <section className="card empty-state" role="alert"><p>IP asset details could not be loaded. Please try again.</p><button className="btn btn-secondary" type="button" onClick={() => void load()}>Try again</button></section>;
  }
  const project = data.asset.project_name || "Unassigned";
  const status = data.asset.unassigned ? "Needs assignment" : "Assigned";
  return (
    <>
      <section className="page-header ip-detail-header">
        <div>
          <p className="eyebrow">IP Asset</p>
          <h1>{data.asset.ip_address}</h1>
          <div className="ip-detail-meta">
            <span className="tag">{data.asset.type}</span>
            <span
              className={`tag${data.asset.project_unassigned ? "" : " tag-project tag-color"}`}
              style={
                data.asset.project_color
                  ? tagColorStyle(data.asset.project_color)
                  : undefined
              }
            >
              Project: {project}
            </span>
            <span className="tag">Host: {data.asset.host_name || "—"}</span>
            <span className={`tag${data.asset.unassigned ? " tag-warning" : ""}`}>Status: {status}</span>
          </div>
        </div>
        {data.can_edit && (
          <div className="header-actions">
            <button className="btn btn-secondary" type="button" onClick={() => setMode("edit")}>Edit</button>
            <button className="btn btn-danger" type="button" onClick={() => setMode("delete")}>Delete</button>
          </div>
        )}
      </section>
      <section className="card">
        <h2>Details</h2>
        <div className="detail-grid">
          <div className="detail-item"><p className="detail-label">IP address</p><p className="detail-value"><a className="link mono" href={`/ui/ip-assets/${data.asset.id}`}>{data.asset.ip_address}</a></p></div>
          <div className="detail-item"><p className="detail-label">Type</p><p className="detail-value">{data.asset.type}</p></div>
          <div className="detail-item"><p className="detail-label">Project</p><p className="detail-value">{project}</p></div>
          <div className="detail-item"><p className="detail-label">Host</p><p className="detail-value">{data.asset.host_id ? <a className="link" href={`/ui/hosts/${data.asset.host_id}`}>{data.asset.host_name}</a> : "—"}</p></div>
          {(data.asset.type === "OS" || data.asset.type === "BMC") && (
            <div className="detail-item">
              <p className="detail-label">{data.asset.type === "OS" ? "BMC address" : "OS address"}</p>
              <p className="detail-value">
                {data.asset.host_pair_assets.length
                  ? data.asset.host_pair_assets.map((pair, index) => (
                      <span key={pair.id}><a className="link mono" href={`/ui/ip-assets/${pair.id}`}>{pair.ip_address}</a>{index < data.asset.host_pair_assets.length - 1 ? ", " : ""}</span>
                    ))
                  : "—"}
              </p>
            </div>
          )}
          <div className="detail-item"><p className="detail-label">Tags</p><p className="detail-value ip-detail-tags">{data.asset.tags.length ? data.asset.tags.map((tag) => <span key={tag.name} className="tag tag-color" style={tagColorStyle(tag.color)}>{tag.name}</span>) : <span className="tag">No tags</span>}</p></div>
          <div className="detail-item"><p className="detail-label">Status</p><p className="detail-value">{status}</p></div>
          <div className="detail-item detail-item-wide"><p className="detail-label">Notes</p><p className="detail-value">{data.asset.notes || "No notes"}</p></div>
        </div>
      </section>
      <AuditLogTable logs={data.audit_logs} />
      <IPAssetDrawer
        mode={mode}
        data={data}
        values={values}
        errors={errors}
        saving={saving}
        dirty={dirty}
        onValues={setValues}
        onClose={close}
        onSubmit={(ack, ip) => void submit(ack, ip)}
        onAutoHost={() => void autoHost()}
      />
    </>
  );
}
