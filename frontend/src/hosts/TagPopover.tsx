import {
  type CSSProperties,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import type { HostTag } from "./types";

interface Props {
  hostName: string;
  tags: HostTag[];
  anchor: HTMLElement;
  onClose: () => void;
  onSelect: (tag: string) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function TagPopover({
  hostName,
  tags,
  anchor,
  onClose,
  onSelect,
  onMouseEnter,
  onMouseLeave,
}: Props) {
  const ref = useRef<HTMLElement>(null);
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState<{ top: number; left: number } | null>(
    null,
  );

  useLayoutEffect(() => {
    function positionPopover() {
      const popover = ref.current;
      if (!popover) return;
      const gutter = 12;
      const gap = 6;
      const anchorRect = anchor.getBoundingClientRect();
      const popoverWidth = Math.min(340, window.innerWidth - gutter * 2);
      const popoverHeight = popover.offsetHeight || 180;
      const below = anchorRect.bottom + gap;
      const top =
        below + popoverHeight <= window.innerHeight - gutter
          ? below
          : Math.max(gutter, anchorRect.top - popoverHeight - gap);
      const left = Math.min(
        window.innerWidth - popoverWidth - gutter,
        Math.max(gutter, anchorRect.left),
      );
      setPosition({ top, left });
    }

    positionPopover();
    window.addEventListener("resize", positionPopover);
    window.addEventListener("scroll", positionPopover, true);
    return () => {
      window.removeEventListener("resize", positionPopover);
      window.removeEventListener("scroll", positionPopover, true);
    };
  }, [anchor]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!ref.current?.contains(target) && !anchor.contains(target)) onClose();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [anchor, onClose]);

  const visibleTags = tags.filter((tag) =>
    tag.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const style = {
    position: "fixed",
    top: position?.top ?? 0,
    left: position?.left ?? 0,
    width: "min(340px, calc(100vw - 24px))",
    visibility: position ? "visible" : "hidden",
  } satisfies CSSProperties;

  return createPortal(
    <section
      ref={ref}
      className="ip-tags-popover hosts-tags-popover"
      role="dialog"
      aria-label={`IP tags for ${hostName}`}
      style={style}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <header className="ip-tags-popover-header">
        <h3 className="ip-tags-popover-title">IP tags for {hostName}</h3>
        <button
          type="button"
          className="ip-tags-popover-close"
          aria-label="Close tags popover"
          onClick={onClose}
        >
          ✕
        </button>
      </header>
      <label className="field ip-tags-popover-search-field">
        <span className="visually-hidden">Filter tags</span>
        <input
          className="input"
          type="search"
          placeholder="Filter tags"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className="ip-tags-popover-list">
        {visibleTags.length ? (
          visibleTags.map((tag) => (
            <button
              key={tag.name}
              className="tag tag-color tag-filter-chip"
              style={{ "--tag-color": tag.color } as React.CSSProperties}
              type="button"
              onClick={() => onSelect(tag.name)}
            >
              {tag.name}
            </button>
          ))
        ) : (
          <p className="muted ip-tags-popover-empty">No matching tags.</p>
        )}
      </div>
    </section>,
    document.body,
  );
}
