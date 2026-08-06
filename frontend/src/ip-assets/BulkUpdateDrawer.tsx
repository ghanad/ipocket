import { type FormEvent, useEffect, useRef } from "react";

import { TagPicker } from "../ip-asset-detail/TagPicker";
import type {
  AssetType,
  BulkValues,
  ColorOption,
} from "./types";

export function BulkUpdateDrawer({
  open,
  initialFocus,
  selectedCount,
  commonTags,
  values,
  projects,
  tags,
  types,
  errors,
  saving,
  onValues,
  onClose,
  onSubmit,
}: {
  open: boolean;
  initialFocus: "edit" | "project" | "tags";
  selectedCount: number;
  commonTags: string[];
  values: BulkValues;
  projects: ColorOption[];
  tags: ColorOption[];
  types: AssetType[];
  errors: string[];
  saving: boolean;
  onValues: (values: BulkValues) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const focusSelector = {
      edit: "select, input, textarea",
      project: '[aria-label="Bulk project action"]',
      tags: '[placeholder="Add tags..."]',
    }[initialFocus];
    ref.current?.querySelector<HTMLElement>(focusSelector)?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [initialFocus, open, onClose]);
  const hasChange = Boolean(
    values.type ||
      values.projectMode ||
      values.tags_to_add.length ||
      values.tags_to_remove.length ||
      values.notes_mode,
  );
  return (
    <>
      <div className={`ip-drawer-overlay${open ? " is-open" : ""}`} aria-hidden="true" onClick={onClose} />
      <aside
        ref={ref}
        className={`ip-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Bulk update IP assets"
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">Bulk update IP assets</h2>
              <p className="ip-drawer-subtitle">Apply one change set to {selectedCount} selected rows.</p>
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
          <form className="ip-drawer-form" id="bulk-ip-assets-form" onSubmit={onSubmit}>
            <section className="ip-drawer-section">
              <h3>Assignment</h3>
              <label className="field">
                <span>Update type</span>
                <select className="select" aria-label="Bulk type" value={values.type} onChange={(event) => onValues({ ...values, type: event.target.value })}>
                  <option value="">Keep current</option>
                  {types.map((type) => <option key={type}>{type}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Project action</span>
                <select
                  className="select"
                  aria-label="Bulk project action"
                  value={values.projectMode}
                  onChange={(event) =>
                    onValues({
                      ...values,
                      projectMode: event.target.value as BulkValues["projectMode"],
                      project_id: "",
                    })
                  }
                >
                  <option value="">Keep current</option>
                  <option value="assign">Assign project</option>
                  <option value="unassign">Unassign project</option>
                </select>
              </label>
              {values.projectMode === "assign" && (
                <label className="field">
                  <span>Project</span>
                  <select className="select" aria-label="Bulk project" value={values.project_id} onChange={(event) => onValues({ ...values, project_id: event.target.value })}>
                    <option value="">Select project</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                  </select>
                </label>
              )}
            </section>
            <section className="ip-drawer-section">
              <h3>Tags</h3>
              <TagPicker catalog={tags} selected={values.tags_to_add} onChange={(selectedTags) => onValues({ ...values, tags_to_add: selectedTags })} />
              <div className="field">
                <span>Common tags to remove</span>
                <div className="tag-filter-selected">
                  {commonTags.length ? commonTags.map((tag) => (
                    <label className="tag tag-muted" key={tag}>
                      <input
                        type="checkbox"
                        checked={values.tags_to_remove.includes(tag)}
                        onChange={(event) =>
                          onValues({
                            ...values,
                            tags_to_remove: event.target.checked
                              ? [...values.tags_to_remove, tag]
                              : values.tags_to_remove.filter((item) => item !== tag),
                          })
                        }
                      />
                      {tag}
                    </label>
                  )) : <span className="muted">No common tags.</span>}
                </div>
              </div>
            </section>
            <section className="ip-drawer-section">
              <h3>Notes</h3>
              <label className="field">
                <span>Notes action</span>
                <select className="select" aria-label="Bulk notes action" value={values.notes_mode} onChange={(event) => onValues({ ...values, notes_mode: event.target.value as BulkValues["notes_mode"] })}>
                  <option value="">Keep current</option>
                  <option value="set">Overwrite notes</option>
                  <option value="clear">Clear notes</option>
                </select>
              </label>
              {values.notes_mode === "set" && (
                <label className="field">
                  <span>Notes</span>
                  <textarea className="textarea" value={values.notes} onChange={(event) => onValues({ ...values, notes: event.target.value })} />
                </label>
              )}
            </section>
          </form>
        </div>
        <div className="ip-drawer-footer">
          <span className="ip-drawer-footer-status">{saving ? "Saving…" : `${selectedCount} selected`}</span>
          <div className="ip-drawer-footer-actions">
            <button className="btn btn-secondary" type="button" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" type="submit" form="bulk-ip-assets-form" disabled={saving || selectedCount === 0 || !hasChange}>Update selected</button>
          </div>
        </div>
      </aside>
    </>
  );
}
