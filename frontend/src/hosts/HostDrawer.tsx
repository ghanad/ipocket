import {
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
} from "react";

import type { FilterOption, HostFormValues, HostRow } from "./types";

interface Props {
  mode: "create" | "edit" | "delete" | null;
  host: HostRow | null;
  values: HostFormValues;
  projects: FilterOption[];
  vendors: FilterOption[];
  errors: string[];
  dirty: boolean;
  saving: boolean;
  acknowledged: boolean;
  confirmName: string;
  onValue: (field: keyof HostFormValues, value: string) => void;
  onAcknowledged: (value: boolean) => void;
  onConfirmName: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function Section({ children }: { children: ReactNode }) {
  return <section className="ip-drawer-section">{children}</section>;
}

export function HostDrawer(props: Props) {
  const ref = useRef<HTMLElement>(null);
  const open = props.mode !== null;

  useEffect(() => {
    if (!open) return;
    ref.current
      ?.querySelector<HTMLElement>("input:not([type='checkbox']), textarea")
      ?.focus();
  }, [open, props.mode]);

  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") props.onClose();
    };
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("keydown", escape);
    };
  }, [open, props.onClose]);

  const deleting = props.mode === "delete";
  const valid =
    deleting
      ? Boolean(
          props.host &&
            props.acknowledged &&
            props.confirmName.trim() === props.host.name,
        )
      : Boolean(props.values.name.trim() && props.dirty);

  return (
    <>
      <div
        className={`ip-drawer-overlay${open ? " is-open" : ""}`}
        aria-hidden="true"
        onClick={props.onClose}
      />
      <aside
        ref={ref}
        className={`ip-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={
          props.mode === "create"
            ? "Add Host"
            : props.mode === "delete"
              ? "Delete Host"
              : "Edit Host"
        }
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">
                {props.mode === "create"
                  ? "New Host"
                  : props.mode === "delete"
                    ? "Delete Host"
                    : "Edit Host"}
              </h2>
              <p className="ip-drawer-subtitle">
                {props.host?.name ?? "Add a physical host to inventory."}
              </p>
            </div>
            <button
              className="ip-drawer-close"
              type="button"
              aria-label="Close drawer"
              onClick={props.onClose}
            >
              ✕
            </button>
          </div>
        </div>
        <div className="ip-drawer-body">
          {props.errors.length > 0 && (
            <div className="alert alert-error" role="alert">
              <ul>
                {props.errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          <form className="ip-drawer-form" id="host-drawer-form" onSubmit={props.onSubmit}>
            {deleting ? (
              <Section>
                <h3 className="ip-drawer-delete-heading">Delete host?</h3>
                <p className="ip-drawer-delete-warning">
                  Linked IP assets will be kept and unassigned from this host.
                </p>
                <dl className="ip-drawer-delete-details">
                  <div>
                    <dt>Name</dt>
                    <dd className="mono">{props.host?.name}</dd>
                  </div>
                  <div>
                    <dt>Linked IPs</dt>
                    <dd>{props.host?.ip_count ?? 0}</dd>
                  </div>
                </dl>
                <label className="field field-inline">
                  <input
                    type="checkbox"
                    checked={props.acknowledged}
                    onChange={(event) =>
                      props.onAcknowledged(event.target.checked)
                    }
                  />
                  <span>I understand this cannot be undone</span>
                </label>
                <label className="field">
                  <span>
                    Type the host name to confirm:{" "}
                    <strong>{props.host?.name}</strong>
                  </span>
                  <input
                    className="input"
                    value={props.confirmName}
                    onChange={(event) =>
                      props.onConfirmName(event.target.value)
                    }
                  />
                </label>
              </Section>
            ) : (
              <>
                <Section>
                  <h3>Basic</h3>
                  <label className="field">
                    <span>Name</span>
                    <input
                      className="input"
                      value={props.values.name}
                      required
                      onChange={(event) =>
                        props.onValue("name", event.target.value)
                      }
                    />
                  </label>
                  <div className="ip-drawer-row ip-drawer-row-two">
                    <label className="field">
                      <span>Vendor</span>
                      <select
                        className="select"
                        value={props.values.vendor_id}
                        onChange={(event) =>
                          props.onValue("vendor_id", event.target.value)
                        }
                      >
                        <option value="">Unassigned</option>
                        {props.vendors.map((vendor) => (
                          <option key={vendor.id} value={vendor.id}>
                            {vendor.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Project</span>
                      <select
                        className="select"
                        value={props.values.project_id}
                        onChange={(event) =>
                          props.onValue("project_id", event.target.value)
                        }
                      >
                        {props.values.project_id === "mixed" && (
                          <option value="mixed">Multiple (keep current)</option>
                        )}
                        <option value="">Unassigned</option>
                        {props.projects.map((project) => (
                          <option key={project.id} value={project.id}>
                            {project.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </Section>
                <Section>
                  <h3>IP Configuration</h3>
                  <div className="ip-drawer-row ip-drawer-row-two">
                    <label className="field">
                      <span>OS IP</span>
                      <input
                        className="input"
                        value={props.values.os_ips}
                        onChange={(event) =>
                          props.onValue("os_ips", event.target.value)
                        }
                      />
                    </label>
                    <label className="field">
                      <span>BMC IP (Out-of-band)</span>
                      <input
                        className="input"
                        value={props.values.bmc_ips}
                        onChange={(event) =>
                          props.onValue("bmc_ips", event.target.value)
                        }
                      />
                    </label>
                  </div>
                </Section>
                <Section>
                  <h3>Notes</h3>
                  <label className="field">
                    <span>Notes</span>
                    <textarea
                      className="textarea"
                      rows={3}
                      value={props.values.notes}
                      onChange={(event) =>
                        props.onValue("notes", event.target.value)
                      }
                    />
                  </label>
                </Section>
              </>
            )}
          </form>
        </div>
        <div className="ip-drawer-footer">
          <span className="ip-drawer-footer-status">
            {props.saving
              ? "Saving…"
              : deleting
                ? "Confirmation required"
                : props.dirty
                  ? "Unsaved changes"
                  : "No changes"}
          </span>
          <div className="ip-drawer-footer-actions">
            <button className="btn btn-secondary" type="button" onClick={props.onClose}>
              Cancel
            </button>
            <button
              className={deleting ? "btn btn-danger" : "btn btn-primary"}
              type="submit"
              form="host-drawer-form"
              disabled={!valid || props.saving}
            >
              {deleting
                ? "Delete permanently"
                : props.mode === "create"
                  ? "Create Host"
                  : "Save changes"}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
