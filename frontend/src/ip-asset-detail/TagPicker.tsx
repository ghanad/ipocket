import { type KeyboardEvent, useMemo, useState } from "react";

import { tagColorStyle } from "../shared/tagColor";
import type { ColorOption } from "./types";

export function TagPicker({
  catalog,
  selected,
  onChange,
}: {
  catalog: ColorOption[];
  selected: string[];
  onChange: (tags: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const available = useMemo(
    () =>
      catalog.filter(
        (tag) =>
          !selected.includes(tag.name) &&
          tag.name.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [catalog, query, selected],
  );
  const add = (name: string) => {
    onChange([...selected, name]);
    setQuery("");
  };
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && available[0]) {
      event.preventDefault();
      add(available[0].name);
    } else if (event.key === "Backspace" && !query && selected.length) {
      onChange(selected.slice(0, -1));
    }
  };
  return (
    <div className="field">
      <span>Tags</span>
      <div className="tag-picker">
        <div className="tag-picker-selected">
          {selected.map((name) => {
            const tag = catalog.find((item) => item.name === name);
            return (
              <button
                key={name}
                className="tag tag-color tag-picker-chip"
                style={tagColorStyle(tag?.color ?? "#e2e8f0")}
                type="button"
                aria-label={`Remove ${name}`}
                onClick={() => onChange(selected.filter((item) => item !== name))}
              >
                {name} <span aria-hidden="true">×</span>
              </button>
            );
          })}
        </div>
        <div className="tag-picker-input-wrap">
          <input
            className="input"
            aria-label="Search tags"
            placeholder="Add tags..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={keyDown}
          />
          {query && (
            <ul className="tag-picker-dropdown">
              {available.length ? (
                available.map((tag) => (
                  <li key={tag.id} className="tag-picker-option">
                    <button
                      className="tag tag-color"
                      style={tagColorStyle(tag.color ?? "#e2e8f0")}
                      type="button"
                      onClick={() => add(tag.name)}
                    >
                      {tag.name}
                    </button>
                  </li>
                ))
              ) : (
                <li className="muted">No matching tags.</li>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
