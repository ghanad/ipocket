import { useEffect, useRef } from "react";

import type { HostTag } from "./types";

interface Props {
  hostName: string;
  tags: HostTag[];
  onClose: () => void;
  onSelect: (tag: string) => void;
}

export function TagPopover({ hostName, tags, onClose, onSelect }: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) onClose();
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
  }, [onClose]);

  return (
    <section
      ref={ref}
      className="ip-tags-popover hosts-tags-popover"
      role="dialog"
      aria-label={`IP tags for ${hostName}`}
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
      <div className="ip-tags-popover-list">
        {tags.map((tag) => (
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
      </div>
    </section>
  );
}
