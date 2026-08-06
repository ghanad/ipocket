import { type FormEvent, useEffect, useRef, useState } from "react";

import { HostSelector } from "./HostSelector";
import { TagPicker } from "./TagPicker";
import type { DetailResponse, EditValues } from "./types";

export function IPAssetDrawer({
  mode,
  data,
  values,
  errors,
  saving,
  dirty,
  onValues,
  onClose,
  onSubmit,
  onAutoHost,
}: {
  mode: "edit" | "delete" | null;
  data: DetailResponse;
  values: EditValues;
  errors: string[];
  saving: boolean;
  dirty: boolean;
  onValues: (values: EditValues) => void;
  onClose: () => void;
  onSubmit: (acknowledged: boolean, confirmIp: string) => void;
  onAutoHost: () => void;
}) {
  const open = mode !== null;
  const ref = useRef<HTMLElement>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmIp, setConfirmIp] = useState("");
  useEffect(() => {
    if (!open) return;
    setAcknowledged(false);
    setConfirmIp("");
    window.setTimeout(() => {
      ref.current?.querySelector<HTMLElement>("select, input, textarea")?.focus();
    }, 0);
  }, [open, mode]);
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);
  const deleting = mode === "delete";
  const hostVisible = values.type === "OS" || values.type === "BMC";
  const canAutoHost =
    data.auto_host_enabled && values.type === "BMC" && !values.host_id;
  const validDelete =
    acknowledged &&
    (!data.delete_requires_exact_ip ||
      confirmIp.trim() === data.asset.ip_address);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(acknowledged, confirmIp);
  };
  return (
    <>
      <div
        className={`ip-drawer-overlay${open ? " is-open" : ""}`}
        aria-hidden="true"
        onClick={onClose}
      />
      <aside
        ref={ref}
        className={`ip-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={deleting ? "Delete IP asset" : "Edit IP asset"}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">
                {deleting ? "Delete IP asset?" : "Edit IP asset"}
              </h2>
              <p className="ip-drawer-subtitle">{data.asset.ip_address}</p>
            </div>
            <button
              className="ip-drawer-close"
              type="button"
              aria-label="Close drawer"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
        </div>
        <div className="ip-drawer-body">
          {errors.length > 0 && (
            <div className="alert alert-error" role="alert">
              <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
            </div>
          )}
          <form className="ip-drawer-form" id="ip-asset-drawer-form" onSubmit={submit}>
            {deleting ? (
              <section className="ip-drawer-section ip-drawer-delete-form">
                <p className="ip-drawer-delete-warning">
                  Permanent and cannot be undone.
                </p>
                <dl className="ip-drawer-delete-details">
                  <div><dt>IP address</dt><dd className="mono">{data.asset.ip_address}</dd></div>
                  <div><dt>Project</dt><dd>{data.asset.project_name || "Unassigned"}</dd></div>
                  <div><dt>Type</dt><dd>{data.asset.type}</dd></div>
                  <div><dt>Host</dt><dd>{data.asset.host_name || "—"}</dd></div>
                </dl>
                <label className="field field-inline">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    onChange={(event) => setAcknowledged(event.target.checked)}
                  />
                  <span>I understand this cannot be undone</span>
                </label>
                {data.delete_requires_exact_ip && (
                  <label className="field">
                    <span>High-risk asset: type the exact IP to confirm</span>
                    <input
                      className="input"
                      value={confirmIp}
                      onChange={(event) => setConfirmIp(event.target.value)}
                    />
                  </label>
                )}
              </section>
            ) : (
              <>
                <section className="ip-drawer-section">
                  <h3>Assignment</h3>
                  <label className="field">
                    <span>IP address</span>
                    <input className="input" value={data.asset.ip_address} readOnly />
                  </label>
                  <div className="ip-drawer-row ip-drawer-row-two">
                    <label className="field">
                      <span>Type</span>
                      <select
                        className="select"
                        aria-label="Type"
                        value={values.type}
                        onChange={(event) => {
                          const type = event.target.value as EditValues["type"];
                          onValues({
                            ...values,
                            type,
                            host_id:
                              type === "OS" || type === "BMC"
                                ? values.host_id
                                : "",
                          });
                        }}
                      >
                        {data.metadata.types.map((type) => <option key={type}>{type}</option>)}
                      </select>
                    </label>
                    <label className="field">
                      <span>Project</span>
                      <select
                        className="select"
                        aria-label="Project"
                        value={values.project_id}
                        onChange={(event) => onValues({ ...values, project_id: event.target.value })}
                      >
                        <option value="">Unassigned</option>
                        {data.metadata.projects.map((project) => (
                          <option key={project.id} value={project.id}>{project.name}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {hostVisible && (
                    <HostSelector
                      hosts={data.metadata.hosts}
                      value={values.host_id}
                      onChange={(host_id) => onValues({ ...values, host_id })}
                    />
                  )}
                  {canAutoHost && (
                    <div className="ip-drawer-auto-host is-visible">
                      <button className="btn btn-outline btn-small" type="button" onClick={onAutoHost}>
                        Create host
                      </button>
                      <p className="ip-drawer-helper">
                        Creates and assigns <span className="mono">server_{data.asset.ip_address}</span>.
                      </p>
                    </div>
                  )}
                </section>
                <section className="ip-drawer-section">
                  <h3>Notes & tags</h3>
                  <TagPicker
                    catalog={data.metadata.tags}
                    selected={values.tags}
                    onChange={(tags) => onValues({ ...values, tags })}
                  />
                  <label className="field">
                    <span>Notes</span>
                    <textarea
                      className="textarea"
                      rows={3}
                      value={values.notes}
                      onChange={(event) => onValues({ ...values, notes: event.target.value })}
                    />
                  </label>
                </section>
              </>
            )}
          </form>
        </div>
        <div className="ip-drawer-footer">
          <span className="ip-drawer-footer-status">
            {saving ? "Saving…" : deleting ? "Confirm deletion" : dirty ? "Unsaved changes" : "No changes"}
          </span>
          <div className="ip-drawer-footer-actions">
            <button className="btn btn-secondary" type="button" onClick={onClose}>Cancel</button>
            <button
              className={deleting ? "btn btn-danger" : "btn btn-primary"}
              type="submit"
              form="ip-asset-drawer-form"
              disabled={saving || (deleting ? !validDelete : !dirty)}
            >
              {deleting ? "Delete permanently" : "Save changes"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
