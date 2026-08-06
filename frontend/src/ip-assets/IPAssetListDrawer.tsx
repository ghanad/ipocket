import { type FormEvent, useEffect, useRef, useState } from "react";

import { HostSelector } from "../ip-asset-detail/HostSelector";
import { TagPicker } from "../ip-asset-detail/TagPicker";
import type {
  AssetFormValues,
  AssetRow,
  AssetType,
  ColorOption,
  HostOption,
} from "./types";

export function IPAssetListDrawer({
  mode,
  asset,
  values,
  types,
  projects,
  hosts,
  tags,
  errors,
  saving,
  dirty,
  onValues,
  onClose,
  onSubmit,
  onAutoHost,
}: {
  mode: "create" | "edit" | "delete" | null;
  asset: AssetRow | null;
  values: AssetFormValues;
  types: AssetType[];
  projects: ColorOption[];
  hosts: HostOption[];
  tags: ColorOption[];
  errors: string[];
  saving: boolean;
  dirty: boolean;
  onValues: (values: AssetFormValues) => void;
  onClose: () => void;
  onSubmit: (acknowledged: boolean, confirmIp: string) => void;
  onAutoHost: () => void;
}) {
  const open = mode !== null;
  const deleting = mode === "delete";
  const creating = mode === "create";
  const ref = useRef<HTMLElement>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmIp, setConfirmIp] = useState("");
  useEffect(() => {
    if (!open) return;
    setAcknowledged(false);
    setConfirmIp("");
    window.setTimeout(() => {
      ref.current?.querySelector<HTMLElement>("input, select, textarea")?.focus();
    }, 0);
  }, [open, mode]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open, onClose]);
  const highRisk = Boolean(asset?.delete_requires_exact_ip);
  const validDelete =
    acknowledged && (!highRisk || confirmIp.trim() === asset?.ip_address);
  const hostVisible = values.type === "OS" || values.type === "BMC";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(acknowledged, confirmIp);
  };

  return (
    <>
      <div className={`ip-drawer-overlay${open ? " is-open" : ""}`} aria-hidden="true" onClick={onClose} />
      <aside
        ref={ref}
        className={`ip-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={creating ? "Add IP" : deleting ? "Delete IP asset" : "Edit IP asset"}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">
                {creating ? "Add IP" : deleting ? "Delete IP asset?" : "Edit IP asset"}
              </h2>
              <p className="ip-drawer-subtitle">
                {asset?.ip_address ?? "Add an address to inventory."}
              </p>
            </div>
            <button className="ip-drawer-close" type="button" aria-label="Close drawer" onClick={onClose}>✕</button>
          </div>
        </div>
        <div className="ip-drawer-body">
          {errors.length > 0 && (
            <div className="alert alert-error" role="alert">
              <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
            </div>
          )}
          <form className="ip-drawer-form" id="ip-assets-drawer-form" onSubmit={submit}>
            {deleting ? (
              <section className="ip-drawer-section ip-drawer-delete-form">
                <p className="ip-drawer-delete-warning">Permanent and cannot be undone.</p>
                <dl className="ip-drawer-delete-details">
                  <div><dt>IP address</dt><dd className="mono">{asset?.ip_address}</dd></div>
                  <div><dt>Project</dt><dd>{asset?.project_name || "Unassigned"}</dd></div>
                  <div><dt>Type</dt><dd>{asset?.type}</dd></div>
                  <div><dt>Host</dt><dd>{asset?.host_name || "—"}</dd></div>
                </dl>
                <label className="field field-inline">
                  <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
                  <span>I understand this cannot be undone</span>
                </label>
                {highRisk && (
                  <label className="field">
                    <span>High-risk asset: type the exact IP to confirm</span>
                    <input className="input" value={confirmIp} onChange={(event) => setConfirmIp(event.target.value)} />
                  </label>
                )}
              </section>
            ) : (
              <>
                <section className="ip-drawer-section">
                  <h3>Assignment</h3>
                  <label className="field">
                    <span>IP address</span>
                    <input
                      className="input"
                      value={values.ip_address}
                      readOnly={!creating}
                      onChange={(event) => onValues({ ...values, ip_address: event.target.value })}
                    />
                  </label>
                  <div className="ip-drawer-row ip-drawer-row-two">
                    <label className="field">
                      <span>Type</span>
                      <select
                        className="select"
                        aria-label="Type"
                        value={values.type}
                        onChange={(event) => {
                          const type = event.target.value as AssetType;
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
                        {types.map((type) => <option key={type}>{type}</option>)}
                      </select>
                    </label>
                    <label className="field">
                      <span>Project</span>
                      <select className="select" aria-label="Project" value={values.project_id} onChange={(event) => onValues({ ...values, project_id: event.target.value })}>
                        <option value="">Unassigned</option>
                        {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                      </select>
                    </label>
                  </div>
                  {hostVisible && (
                    <HostSelector
                      hosts={hosts}
                      value={values.host_id}
                      onChange={(host_id) => onValues({ ...values, host_id })}
                    />
                  )}
                  {!creating && asset?.can_auto_host && values.type === "BMC" && !values.host_id && (
                    <div className="ip-drawer-auto-host is-visible">
                      <button className="btn btn-outline btn-small" type="button" onClick={onAutoHost}>Create host</button>
                      <p className="ip-drawer-helper">Creates and assigns <span className="mono">server_{values.ip_address}</span>.</p>
                    </div>
                  )}
                </section>
                <section className="ip-drawer-section">
                  <h3>Notes & tags</h3>
                  <TagPicker catalog={tags} selected={values.tags} onChange={(selectedTags) => onValues({ ...values, tags: selectedTags })} />
                  <label className="field">
                    <span>Notes</span>
                    <textarea className="textarea" rows={3} value={values.notes} onChange={(event) => onValues({ ...values, notes: event.target.value })} />
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
              form="ip-assets-drawer-form"
              disabled={saving || (deleting ? !validDelete : !dirty)}
            >
              {creating ? "Create" : deleting ? "Delete permanently" : "Save changes"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
