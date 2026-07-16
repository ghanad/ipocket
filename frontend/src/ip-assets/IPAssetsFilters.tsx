import { type FormEvent, useState } from "react";

import type {
  AssetFilters,
  ColorOption,
  TagMode,
} from "./types";

export function IPAssetsFilters({
  filters,
  projects,
  tags,
  types,
  onChange,
}: {
  filters: AssetFilters;
  projects: ColorOption[];
  tags: ColorOption[];
  types: string[];
  onChange: (patch: Partial<AssetFilters>) => void;
}) {
  const [mode, setMode] = useState<TagMode>("tag_any");
  const [tagInput, setTagInput] = useState("");
  const catalog = new Map(tags.map((tag) => [tag.name, tag]));

  function addTagName(rawName: string) {
    const name = rawName.trim().toLowerCase();
    if (!catalog.has(name) || filters[mode].includes(name)) return;
    onChange({ [mode]: [...filters[mode], name] });
    setTagInput("");
  }

  function addTag(event: FormEvent) {
    event.preventDefault();
    addTagName(tagInput);
  }

  return (
    <section className="card filter-card">
      <div className="filters-grid">
        <label className="field">
          <span>Search</span>
          <input
            className="input"
            type="search"
            placeholder="IP or notes"
            value={filters.q}
            onChange={(event) => onChange({ q: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Project</span>
          <select
            className="select"
            aria-label="Project"
            value={filters.project_id}
            onChange={(event) => onChange({ project_id: event.target.value })}
          >
            <option value="">All</option>
            <option value="unassigned">Unassigned</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Type</span>
          <select
            className="select"
            aria-label="Type filter"
            value={filters.type}
            onChange={(event) => onChange({ type: event.target.value })}
          >
            <option value="">All</option>
            {types.map((type) => <option key={type}>{type}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Assignment</span>
          <select
            className="select"
            aria-label="Assignment"
            value={String(filters.unassigned_only)}
            onChange={(event) =>
              onChange({ unassigned_only: event.target.value === "true" })
            }
          >
            <option value="false">All</option>
            <option value="true">Unassigned only</option>
          </select>
        </label>
        <label className="field">
          <span>Status</span>
          <select
            className="select"
            aria-label="Status"
            value={String(filters.archived_only)}
            onChange={(event) =>
              onChange({ archived_only: event.target.value === "true" })
            }
          >
            <option value="false">Active only</option>
            <option value="true">Archived only</option>
          </select>
        </label>
        <div className="field field-tag-filter">
          <span>Tags</span>
          <form className="tag-filter-controls" onSubmit={addTag}>
            <input
              className="input"
              aria-label="Tag filter"
              placeholder="Type tag and press Enter"
              list="ip-assets-tag-suggestions"
              value={tagInput}
              onChange={(event) => {
                const nextValue = event.target.value;
                setTagInput(nextValue);
                if (catalog.has(nextValue.trim().toLowerCase())) {
                  addTagName(nextValue);
                }
              }}
            />
            <div className="tag-filter-mode-controls" role="group" aria-label="Tag filter mode">
              {(["tag_any", "tag_all", "tag_not"] as TagMode[]).map((item) => (
                <button
                  key={item}
                  className={`tag-filter-mode${mode === item ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setMode(item)}
                >
                  {item === "tag_any" ? "OR" : item === "tag_all" ? "AND" : "NOT"}
                </button>
              ))}
            </div>
          </form>
          <datalist id="ip-assets-tag-suggestions">
            {tags.map((tag) => <option key={tag.id} value={tag.name} />)}
          </datalist>
          <div className="tag-filter-groups">
            {(["tag_any", "tag_all", "tag_not"] as TagMode[]).map((item) => (
              <div className="tag-filter-group" key={item}>
                <span className="tag-filter-group-label">
                  {item === "tag_any" ? "OR" : item === "tag_all" ? "AND" : "NOT"}
                </span>
                <div className="tag-filter-selected">
                  {filters[item].map((name) => (
                    <span className="tag-filter-entry" key={name}>
                      <button
                        className="tag tag-color tag-filter-chip"
                        style={
                          {
                            "--tag-color":
                              catalog.get(name)?.color ?? "#e2e8f0",
                          } as React.CSSProperties
                        }
                        type="button"
                        onClick={() =>
                          onChange({
                            [item]: filters[item].filter(
                              (tag) => tag !== name,
                            ),
                          })
                        }
                      >
                        {name} ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
