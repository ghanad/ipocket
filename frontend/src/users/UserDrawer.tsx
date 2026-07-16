import {
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
} from "react";

interface UserDrawerProps {
  open: boolean;
  formId: string;
  label: string;
  title: string;
  subtitle: string;
  errors: string[];
  footerStatus: string;
  primaryLabel: string;
  primaryClassName?: string;
  primaryDisabled: boolean;
  initialFocus?: "first" | "confirm";
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}

const focusableSelector = [
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[href]",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function UserDrawer({
  open,
  formId,
  label,
  title,
  subtitle,
  errors,
  footerStatus,
  primaryLabel,
  primaryClassName = "btn btn-primary",
  primaryDisabled,
  initialFocus = "first",
  onClose,
  onSubmit,
  children,
}: UserDrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const selector =
      initialFocus === "confirm"
        ? "[data-user-confirm]"
        : "input:not([disabled]):not([type='checkbox'])";
    const timeout = window.setTimeout(() => {
      drawerRef.current?.querySelector<HTMLElement>(selector)?.focus();
    }, 100);
    return () => window.clearTimeout(timeout);
  }, [initialFocus, open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        drawerRef.current?.querySelectorAll<HTMLElement>(focusableSelector) ?? [],
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  return (
    <>
      <div
        className={`ip-drawer-overlay${open ? " is-open" : ""}`}
        aria-hidden="true"
        onClick={onClose}
      />
      <aside
        ref={drawerRef}
        className={`ip-drawer${open ? " is-open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="ip-drawer-header">
          <div className="ip-drawer-header-row">
            <div>
              <h2 className="ip-drawer-title">{title}</h2>
              <p className="ip-drawer-subtitle">{subtitle}</p>
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
              <ul>
                {errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          <form className="ip-drawer-form" id={formId} onSubmit={onSubmit}>
            {children}
          </form>
        </div>
        <div className="ip-drawer-footer">
          <span className="ip-drawer-footer-status">{footerStatus}</span>
          <div className="ip-drawer-footer-actions">
            <button className="btn btn-secondary" type="button" onClick={onClose}>
              Cancel
            </button>
            <button
              className={primaryClassName}
              type="submit"
              form={formId}
              disabled={primaryDisabled}
            >
              {primaryLabel}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
