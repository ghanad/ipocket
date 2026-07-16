import { useState } from "react";

import { TagOverflowPopover } from "./TagOverflowPopover";
import type { AssetRow } from "./types";

export function IPAssetsTable({
  assets,
  canEdit,
  selected,
  onSelected,
  onQuickFilter,
  onEdit,
  onDelete,
  footer,
}: {
  assets: AssetRow[];
  canEdit: boolean;
  selected: Set<number>;
  onSelected: (ids: Set<number>) => void;
  onQuickFilter: (name: string, value: string) => void;
  onEdit: (asset: AssetRow) => void;
  onDelete: (asset: AssetRow) => void;
  footer?: React.ReactNode;
}) {
  const [popover, setPopover] = useState<{
    asset: AssetRow;
    anchor: HTMLElement;
  } | null>(null);
  const pageIds = assets.map((asset) => asset.id);
  const allSelected =
    pageIds.length > 0 && pageIds.every((assetId) => selected.has(assetId));

  if (!assets.length) {
    return (
      <section className="card table-card">
        <p className="empty-state">No IP assets found.</p>
      </section>
    );
  }

  return (
    <section className="card table-card">
      {canEdit && (
        <div className="bulk-edit-controls">
          <label className="field field-inline">
            <input
              className="checkbox"
              type="checkbox"
              aria-label="Select all IP assets"
              checked={allSelected}
              onChange={(event) => {
                const next = new Set(selected);
                pageIds.forEach((id) =>
                  event.target.checked ? next.add(id) : next.delete(id),
                );
                onSelected(next);
              }}
            />
            <span>Select all</span>
          </label>
          <span className="muted">{selected.size} selected</span>
        </div>
      )}
      <div className="table-wrapper">
        <table className={`table table-ip-assets${canEdit ? "" : " table-ip-assets-readonly"}`}>
          <thead>
            <tr>
              {canEdit && <th><span className="visually-hidden">Select</span></th>}
              <th className="col-ip-address">IP address</th>
              <th className="col-project">Project</th>
              <th className="col-type">Type</th>
              <th>Tags</th>
              <th>Notes</th>
              {canEdit && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {assets.map((asset) => {
              const visibleTags =
                asset.tags.length > 3 ? asset.tags.slice(0, 2) : asset.tags;
              return (
                <tr key={asset.id}>
                  {canEdit && (
                    <td>
                      <input
                        className="checkbox"
                        type="checkbox"
                        aria-label={`Select ${asset.ip_address}`}
                        checked={selected.has(asset.id)}
                        onChange={(event) => {
                          const next = new Set(selected);
                          event.target.checked
                            ? next.add(asset.id)
                            : next.delete(asset.id);
                          onSelected(next);
                        }}
                      />
                    </td>
                  )}
                  <td className="mono col-ip-address">
                    <a href={`/ui/ip-assets/${asset.id}`}>{asset.ip_address}</a>
                  </td>
                  <td className="col-project">
                    {asset.project_unassigned ? (
                      <button
                        className="tag tag-warning tag-filter-chip"
                        type="button"
                        onClick={() => onQuickFilter("project_id", "unassigned")}
                      >
                        Unassigned
                      </button>
                    ) : (
                      <button
                        className="tag tag-project tag-filter-chip"
                        style={
                          {
                            "--project-color":
                              asset.project_color || "#94a3b8",
                          } as React.CSSProperties
                        }
                        type="button"
                        onClick={() =>
                          onQuickFilter("project_id", String(asset.project_id))
                        }
                      >
                        {asset.project_name}
                      </button>
                    )}
                  </td>
                  <td className="col-type">
                    <button
                      className="tag tag-color tag-filter-chip"
                      type="button"
                      onClick={() => onQuickFilter("type", asset.type)}
                    >
                      {asset.type}
                    </button>
                  </td>
                  <td className="ip-tags-cell">
                    {asset.tags.length ? (
                      <div className="ip-tags-inline" aria-label={`Tags for ${asset.ip_address}`}>
                        {visibleTags.map((tag) => (
                          <button
                            key={tag.name}
                            className="tag tag-color tag-filter-chip"
                            style={
                              { "--tag-color": tag.color } as React.CSSProperties
                            }
                            type="button"
                            onClick={() => onQuickFilter("tag_any", tag.name)}
                          >
                            {tag.name}
                          </button>
                        ))}
                        {asset.tags.length > 3 && (
                          <button
                            className="tag tag-muted ip-tags-more"
                            type="button"
                            aria-haspopup="dialog"
                            aria-expanded={popover?.asset.id === asset.id}
                            onClick={(event) =>
                              setPopover({
                                asset,
                                anchor: event.currentTarget,
                              })
                            }
                          >
                            +{asset.tags.length - 2} more
                          </button>
                        )}
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="ip-note-cell">
                    {asset.notes ? (
                      <span
                        className="ip-note-preview muted"
                        tabIndex={0}
                        title={asset.notes}
                        data-full-note={asset.notes}
                      >
                        {asset.notes}
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  {canEdit && (
                    <td className="asset-actions-cell">
                      <div className="ip-asset-actions">
                        <button className="btn btn-secondary btn-small" type="button" onClick={() => onEdit(asset)}>Edit</button>
                        <button className="btn btn-danger btn-small" type="button" onClick={() => onDelete(asset)}>Delete</button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {footer}
      {popover && (
        <TagOverflowPopover
          asset={popover.asset}
          anchor={popover.anchor}
          onClose={() => setPopover(null)}
          onSelect={(tag) => {
            onQuickFilter("tag_any", tag);
            setPopover(null);
          }}
        />
      )}
    </section>
  );
}
