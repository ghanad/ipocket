import { useEffect, useState } from "react";

import type { AssetRow } from "./types";

export function TagOverflowPopover({
  asset,
  anchor,
  onClose,
  onSelect,
  onMouseEnter,
  onMouseLeave,
}: {
  asset: AssetRow;
  anchor: HTMLElement;
  onClose: () => void;
  onSelect: (tag: string) => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const [query, setQuery] = useState("");
  const rect = anchor.getBoundingClientRect();
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [onClose]);
  const visible = asset.tags.filter((tag) =>
    tag.name.toLowerCase().includes(query.trim().toLowerCase()),
  );
  return (
    <div
      className="ip-tags-popover"
      role="dialog"
      aria-label={`Tags for ${asset.ip_address}`}
      style={{ position: "fixed", top: rect.bottom + 6, left: rect.left }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="ip-tags-popover-header">
        <h3 className="ip-tags-popover-title">Tags</h3>
        <button className="ip-tags-popover-close" type="button" aria-label="Close tags" onClick={onClose}>✕</button>
      </div>
      <label className="field ip-tags-popover-search-field">
        <span className="visually-hidden">Filter tags</span>
        <input
          className="input"
          aria-label="Filter tags"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      <div className="ip-tags-popover-list">
        {visible.map((tag) => (
          <button
            key={tag.name}
            className="tag tag-color tag-filter-chip"
            style={{ "--tag-color": tag.color } as React.CSSProperties}
            type="button"
            onClick={() => onSelect(tag.name)}
          >
            {tag.name}
          </button>
        ))}
        {!visible.length && <p className="muted">No matching tags.</p>}
      </div>
    </div>
  );
}
