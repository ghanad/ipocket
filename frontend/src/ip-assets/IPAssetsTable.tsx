import { useEffect, useRef, useState } from "react";

import { RowActions } from "../shared/RowActions";
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
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const pageIds = assets.map((asset) => asset.id);
  const allSelected =
    pageIds.length > 0 && pageIds.every((assetId) => selected.has(assetId));

  function clearOpenTimer() {
    if (openTimer.current !== null) {
      window.clearTimeout(openTimer.current);
      openTimer.current = null;
    }
  }

  function clearCloseTimer() {
    if (closeTimer.current !== null) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }

  function openPopover(
    asset: AssetRow,
    anchor: HTMLElement,
    delay = 0,
  ) {
    clearOpenTimer();
    clearCloseTimer();
    if (delay === 0) {
      setPopover({ asset, anchor });
      return;
    }
    openTimer.current = window.setTimeout(() => {
      setPopover({ asset, anchor });
      openTimer.current = null;
    }, delay);
  }

  function scheduleClose() {
    clearOpenTimer();
    clearCloseTimer();
    closeTimer.current = window.setTimeout(() => {
      setPopover(null);
      closeTimer.current = null;
    }, 180);
  }

  useEffect(
    () => () => {
      clearOpenTimer();
      clearCloseTimer();
    },
    [],
  );

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
              {canEdit && <th className="asset-actions-cell">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {assets.map((asset) => {
              const visibleTags =
                asset.tags.length > 3 ? asset.tags.slice(0, 2) : asset.tags;
              return (
                <tr
                  key={asset.id}
                  className={canEdit ? "row-with-actions" : undefined}
                  tabIndex={canEdit ? 0 : undefined}
                >
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
                            onMouseEnter={(event) =>
                              openPopover(asset, event.currentTarget, 120)
                            }
                            onMouseLeave={scheduleClose}
                            onFocus={(event) =>
                              openPopover(asset, event.currentTarget)
                            }
                            onClick={(event) =>
                              openPopover(asset, event.currentTarget)
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
                      <RowActions
                        itemLabel={asset.ip_address}
                        onEdit={() => onEdit(asset)}
                        actions={[
                          {
                            label: "Delete",
                            destructive: true,
                            onSelect: () => onDelete(asset),
                          },
                        ]}
                      />
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
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
          onSelect={(tag) => {
            onQuickFilter("tag_any", tag);
            setPopover(null);
          }}
        />
      )}
    </section>
  );
}
