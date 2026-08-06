import {
  type CSSProperties,
  type KeyboardEvent,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

export interface RowMenuAction {
  label: string;
  onSelect: () => void;
  destructive?: boolean;
  disabled?: boolean;
  disabledReason?: string | null;
}

interface Props {
  itemLabel: string;
  onEdit: () => void;
  actions: RowMenuAction[];
}

const VIEWPORT_GAP = 8;
const MENU_OFFSET = 6;

function DeleteIcon() {
  return (
    <svg
      aria-hidden="true"
      className="row-action-item-icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
    >
      <path
        d="M5.5 2.5h5M3.5 4.5h9m-8 0 .5 9h6l.5-9M6.5 6.5v5m3-5v5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.4"
      />
    </svg>
  );
}

export function RowActions({ itemLabel, onEdit, actions }: Props) {
  const menuId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<CSSProperties>({
    left: VIEWPORT_GAP,
    top: VIEWPORT_GAP,
  });

  function closeMenu(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) {
      window.setTimeout(() => triggerRef.current?.focus(), 0);
    }
  }

  function positionMenu() {
    const trigger = triggerRef.current;
    const menu = menuRef.current;
    if (!trigger || !menu) return;

    const triggerRect = trigger.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    const direction = window.getComputedStyle(trigger).direction;
    const preferredLeft =
      direction === "rtl"
        ? triggerRect.left
        : triggerRect.right - menuRect.width;
    const left = Math.min(
      Math.max(VIEWPORT_GAP, preferredLeft),
      Math.max(VIEWPORT_GAP, window.innerWidth - menuRect.width - VIEWPORT_GAP),
    );
    const below = triggerRect.bottom + MENU_OFFSET;
    const top =
      below + menuRect.height <= window.innerHeight - VIEWPORT_GAP
        ? below
        : Math.max(VIEWPORT_GAP, triggerRect.top - menuRect.height - MENU_OFFSET);

    setPosition({ left, top });
  }

  useLayoutEffect(() => {
    if (!open) return;
    positionMenu();
    menuRef.current
      ?.querySelector<HTMLElement>('[role="menuitem"]')
      ?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !triggerRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        closeMenu();
      }
    };
    const handleFocusIn = (event: FocusEvent) => {
      const target = event.target as Node;
      if (
        !triggerRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        closeMenu();
      }
    };
    const handleViewportChange = () => positionMenu();

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("focusin", handleFocusIn);
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("focusin", handleFocusIn);
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [open]);

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
    }
  }

  function handleMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
    );
    const currentIndex = items.indexOf(document.activeElement as HTMLElement);

    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key === "Tab") {
      closeMenu();
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;

    event.preventDefault();
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? items.length - 1
          : event.key === "ArrowDown"
            ? (currentIndex + 1) % items.length
            : (currentIndex - 1 + items.length) % items.length;
    items[nextIndex]?.focus();
  }

  return (
    <div className={`row-actions${open ? " is-open" : ""}`}>
      <button
        className="row-action-control row-actions-edit"
        type="button"
        title={`Edit ${itemLabel}`}
        onClick={onEdit}
      >
        Edit
      </button>
      <button
        ref={triggerRef}
        className="row-action-control row-actions-trigger"
        type="button"
        aria-label={`More actions for ${itemLabel}`}
        title={`More actions for ${itemLabel}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className="row-actions-icon" aria-hidden="true">
          ⋯
        </span>
      </button>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            id={menuId}
            className="row-actions-panel"
            role="menu"
            aria-label={`Actions for ${itemLabel}`}
            style={position}
            onKeyDown={handleMenuKeyDown}
          >
            {actions.map((action, index) => (
              <div key={action.label}>
                {action.destructive &&
                  index > 0 &&
                  !actions[index - 1]?.destructive && (
                    <div className="row-actions-separator" role="separator" />
                  )}
                <button
                  className={`row-action-item${
                    action.destructive ? " row-action-item-danger" : ""
                  }`}
                  type="button"
                  role="menuitem"
                  aria-label={`${action.label} ${itemLabel}`}
                  aria-disabled={action.disabled || undefined}
                  title={action.disabledReason ?? undefined}
                  onClick={() => {
                    if (action.disabled) return;
                    closeMenu();
                    action.onSelect();
                  }}
                >
                  {action.destructive && <DeleteIcon />}
                  <span>{action.label}</span>
                  {action.disabledReason && (
                    <span className="visually-hidden">
                      {` ${action.disabledReason}`}
                    </span>
                  )}
                </button>
              </div>
            ))}
          </div>,
          document.body,
        )}
    </div>
  );
}
