import {
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";

import { RowActions } from "../shared/RowActions";
import { TagPopover } from "./TagPopover";
import type { HostRow } from "./types";

interface Props {
  hosts: HostRow[];
  canEdit: boolean;
  onEdit: (host: HostRow) => void;
  onDelete: (host: HostRow) => void;
  onTag: (tag: string) => void;
  footer?: ReactNode;
}

export function HostsTable({
  hosts,
  canEdit,
  onEdit,
  onDelete,
  onTag,
  footer,
}: Props) {
  const [popover, setPopover] = useState<{
    host: HostRow;
    anchor: HTMLElement;
  } | null>(null);
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);

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

  function openPopover(host: HostRow, anchor: HTMLElement, delay = 0) {
    clearOpenTimer();
    clearCloseTimer();
    if (delay === 0) {
      setPopover({ host, anchor });
      return;
    }
    openTimer.current = window.setTimeout(() => {
      setPopover({ host, anchor });
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

  if (!hosts.length) {
    return (
      <section className="card table-card">
        <p className="empty-state">No hosts found.</p>
      </section>
    );
  }

  return (
    <section className="card table-card">
      <div className="table-wrapper table-wrapper-hosts">
        <table className="table table-hosts">
          <thead>
            <tr>
              <th>Host name</th>
              <th>Vendor</th>
              <th>Project</th>
              <th>OS IPs</th>
              <th>BMC IPs</th>
              <th>IP tags</th>
              <th>Linked IPs</th>
              {canEdit && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {hosts.map((host) => (
              <tr
                key={host.id}
                className={canEdit ? "row-with-actions" : undefined}
                tabIndex={canEdit ? 0 : undefined}
              >
                <td>
                  <a href={`/ui/hosts/${host.id}`}>{host.name}</a>
                </td>
                <td>{host.vendor ?? ""}</td>
                <td>
                  {host.project_count === 0 ? (
                    <span className="tag tag-warning">Unassigned</span>
                  ) : host.project_count > 1 ? (
                    <span className="tag tag-warning">Multiple</span>
                  ) : (
                    <span
                      className="tag tag-project"
                      style={
                        {
                          "--project-color":
                            host.project_color || "#94a3b8",
                        } as React.CSSProperties
                      }
                    >
                      {host.project_name}
                    </span>
                  )}
                </td>
                <td>
                  {host.os_ip_links.map((asset, index) => (
                    <span key={asset.id}>
                      {index > 0 && ", "}
                      <a className="mono" href={`/ui/ip-assets/${asset.id}`}>
                        {asset.ip_address}
                      </a>
                    </span>
                  ))}
                </td>
                <td>
                  {host.bmc_ip_links.map((asset, index) => (
                    <span key={asset.id}>
                      {index > 0 && ", "}
                      <a className="mono" href={`/ui/ip-assets/${asset.id}`}>
                        {asset.ip_address}
                      </a>
                    </span>
                  ))}
                </td>
                <td className="host-ip-tags-cell">
                  <div className="host-ip-tags-inline ip-tags-inline">
                    {host.ip_tags.slice(0, 2).map((tag) => (
                      <button
                        key={tag.name}
                        className="tag tag-color tag-filter-chip"
                        style={
                          { "--tag-color": tag.color } as React.CSSProperties
                        }
                        type="button"
                        onClick={() => onTag(tag.name)}
                      >
                        {tag.name}
                      </button>
                    ))}
                    {host.ip_tags.length > 2 && (
                      <button
                        className="tag tag-muted ip-tags-more"
                        type="button"
                        aria-haspopup="dialog"
                        aria-expanded={popover?.host.id === host.id}
                        onMouseEnter={(event) =>
                          openPopover(host, event.currentTarget, 120)
                        }
                        onMouseLeave={scheduleClose}
                        onFocus={(event) =>
                          openPopover(host, event.currentTarget)
                        }
                        onClick={(event) => {
                          event.stopPropagation();
                          openPopover(host, event.currentTarget);
                        }}
                      >
                        +{host.ip_tags.length - 2} more
                      </button>
                    )}
                  </div>
                </td>
                <td>{host.ip_count}</td>
                {canEdit && (
                  <td className="asset-actions-cell">
                    <RowActions
                      itemLabel={host.name}
                      onEdit={() => onEdit(host)}
                      actions={[
                        {
                          label: "Delete",
                          destructive: true,
                          onSelect: () => onDelete(host),
                        },
                      ]}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer}
      {popover && (
        <TagPopover
          hostName={popover.host.name}
          tags={popover.host.ip_tags}
          anchor={popover.anchor}
          onClose={() => setPopover(null)}
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
          onSelect={(tag) => {
            onTag(tag);
            setPopover(null);
          }}
        />
      )}
    </section>
  );
}
