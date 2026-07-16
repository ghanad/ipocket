import { type KeyboardEvent, useState } from "react";

import { tagColorStyle } from "../shared/tagColor";
import type { FilterOption, HostFilters } from "./types";

interface Props {
  filters: HostFilters;
  projects: FilterOption[];
  vendors: FilterOption[];
  tags: FilterOption[];
  onChange: (patch: Partial<HostFilters>) => void;
}

export function HostsFilters({
  filters,
  projects,
  vendors,
  tags,
  onChange,
}: Props) {
  const [tagInput, setTagInput] = useState("");

  function addTag(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const match = tags.find(
      (tag) => tag.name.toLowerCase() === tagInput.trim().toLowerCase(),
    );
    if (match && !filters.tags.includes(match.name)) {
      onChange({ tags: [...filters.tags, match.name] });
    }
    setTagInput("");
  }

  return (
    <details
      className="card compact-card collapsible-card filter-card"
      open={Boolean(
        filters.q ||
          filters.project_id ||
          filters.unassigned_only ||
          filters.status ||
          filters.vendor_id ||
          filters.tags.length,
      )}
    >
      <summary className="card-header collapsible-summary">
        <div>
          <h2>Search Hosts</h2>
          <p className="subtitle">
            Filter by host name, vendor, project, notes, linked IPs, or tags.
          </p>
        </div>
        <span className="collapsible-indicator" aria-hidden="true">
          ▸
        </span>
      </summary>
      <div className="filters-grid">
        <label className="field">
          <span>Search</span>
          <input
            className="input"
            type="search"
            value={filters.q}
            placeholder="Name, vendor, project, notes, or IP"
            onChange={(event) => onChange({ q: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Project</span>
          <select
            className="select"
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
          <span>Assignment</span>
          <select
            className="select"
            value={filters.unassigned_only ? "true" : "false"}
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
            value={filters.status}
            onChange={(event) => onChange({ status: event.target.value })}
          >
            <option value="">All</option>
            <option value="linked">Linked IPs</option>
            <option value="free">No linked IPs</option>
          </select>
        </label>
        <label className="field">
          <span>Vendor</span>
          <select
            className="select"
            value={filters.vendor_id}
            onChange={(event) => onChange({ vendor_id: event.target.value })}
          >
            <option value="">All</option>
            {vendors.map((vendor) => (
              <option key={vendor.id} value={vendor.id}>
                {vendor.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field field-tag-filter">
          <span>Tags</span>
          <input
            className="input"
            value={tagInput}
            list="host-tag-filter-suggestions"
            placeholder="Type tag and press Enter"
            onChange={(event) => setTagInput(event.target.value)}
            onKeyDown={addTag}
          />
          <datalist id="host-tag-filter-suggestions">
            {tags.map((tag) => (
              <option key={tag.id} value={tag.name} />
            ))}
          </datalist>
          <div className="tag-filter-selected">
            {filters.tags.map((tagName) => {
              const tag = tags.find((item) => item.name === tagName);
              return (
                <button
                  key={tagName}
                  className="tag tag-color tag-filter-chip"
                  style={tagColorStyle(tag?.color ?? "#e2e8f0")}
                  type="button"
                  onClick={() =>
                    onChange({
                      tags: filters.tags.filter((item) => item !== tagName),
                    })
                  }
                >
                  {tagName} ×
                </button>
              );
            })}
          </div>
        </label>
      </div>
    </details>
  );
}
