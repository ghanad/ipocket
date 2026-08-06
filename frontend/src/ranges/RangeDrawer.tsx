import {
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
} from "react";

interface RangeDrawerProps {
  open: boolean;
  label: string;
  title: string;
  subtitle: string;
  errors: string[];
  footerStatus: string;
  primaryLabel: string;
  primaryClassName: string;
  primaryDisabled: boolean;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
  initialFocus?: "first" | "confirm";
}

export function RangeDrawer({
  open,
  label,
  title,
  subtitle,
  errors,
  footerStatus,
  primaryLabel,
  primaryClassName,
  primaryDisabled,
  onClose,
  onSubmit,
  children,
  initialFocus = "first",
}: RangeDrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const selector =
      initialFocus === "confirm"
        ? "[data-range-confirm]"
        : "input:not([type='checkbox']), textarea";
    const timeout = window.setTimeout(() => {
      drawerRef.current?.querySelector<HTMLElement>(selector)?.focus();
    }, 100);
    return () => window.clearTimeout(timeout);
  }, [initialFocus, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
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
          <form
            className="ip-drawer-form"
            id={`range-${label.toLowerCase().replaceAll(" ", "-")}-form`}
            onSubmit={onSubmit}
          >
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
              form={`range-${label.toLowerCase().replaceAll(" ", "-")}-form`}
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
