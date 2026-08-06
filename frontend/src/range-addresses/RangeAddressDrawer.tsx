import { type FormEvent, useEffect, useRef } from "react";

import { TagPicker } from "../ip-asset-detail/TagPicker";
import type { AddressFormValues, ColorOption } from "./types";

export function RangeAddressDrawer({
  mode,
  values,
  initialValues,
  projects,
  tags,
  types,
  errors,
  saving,
  onValues,
  onClose,
  onSubmit,
}: {
  mode: "add" | "edit" | null;
  values: AddressFormValues;
  initialValues: AddressFormValues;
  projects: ColorOption[];
  tags: ColorOption[];
  types: string[];
  errors: string[];
  saving: boolean;
  onValues: (values: AddressFormValues) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const open = mode !== null;
  const ref = useRef<HTMLElement>(null);
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  useEffect(() => {
    if (!open) return;
    window.setTimeout(
      () => ref.current?.querySelector<HTMLElement>("select, input, textarea")?.focus(),
      0,
    );
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open, mode, onClose]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit();
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
        aria-label={mode === "add" ? "Add IP asset" : "Edit IP asset"}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">
                {mode === "add" ? "Add IP asset" : "Edit IP asset"}
              </h2>
              <p className="ip-drawer-subtitle">{values.ip_address || "—"}</p>
            </div>
            <button className="ip-drawer-close" type="button" aria-label="Close drawer" onClick={onClose}>✕</button>
          </div>
        </div>
        <div className="ip-drawer-body">
          {errors.length > 0 && (
            <div className="alert alert-error" role="alert">
              <p className="alert-title">Fix the following:</p>
              <ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul>
            </div>
          )}
          <form className="ip-drawer-form" id="range-address-form" onSubmit={submit}>
            <section className="ip-drawer-section">
              <h3>Assignment</h3>
              <label className="field">
                <span>IP address</span>
                <input className="input" value={values.ip_address} readOnly />
              </label>
              <div className="ip-drawer-row ip-drawer-row-two">
                <label className="field">
                  <span>Type</span>
                  <select className="select" aria-label="Type" value={values.type} onChange={(event) => onValues({ ...values, type: event.target.value })}>
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
            </section>
            <section className="ip-drawer-section">
              <h3>Notes & tags</h3>
              <TagPicker catalog={tags} selected={values.tags} onChange={(selected) => onValues({ ...values, tags: selected })} />
              <label className="field">
                <span>Notes</span>
                <textarea className="textarea" rows={3} value={values.notes} onChange={(event) => onValues({ ...values, notes: event.target.value })} />
              </label>
            </section>
          </form>
        </div>
        <div className="ip-drawer-footer">
          <span className="ip-drawer-footer-status">{saving ? "Saving…" : dirty ? "Unsaved changes" : "No changes"}</span>
          <div className="ip-drawer-footer-actions">
            <button className="btn btn-secondary" type="button" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" type="submit" form="range-address-form" disabled={saving || !dirty}>
              {saving ? "Saving…" : mode === "add" ? "Allocate" : "Save changes"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
