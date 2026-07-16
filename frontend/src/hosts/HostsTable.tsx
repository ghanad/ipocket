import { useState } from "react";

import { TagPopover } from "./TagPopover";
import type { HostRow } from "./types";

interface Props {
  hosts: HostRow[];
  canEdit: boolean;
  onEdit: (host: HostRow) => void;
  onDelete: (host: HostRow) => void;
  onTag: (tag: string) => void;
}

export function HostsTable({
  hosts,
  canEdit,
  onEdit,
  onDelete,
  onTag,
}: Props) {
  const [popoverHost, setPopoverHost] = useState<HostRow | null>(null);

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
              <tr key={host.id}>
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
                        aria-expanded={popoverHost?.id === host.id}
                        onClick={(event) => {
                          event.stopPropagation();
                          setPopoverHost(host);
                        }}
                      >
                        +{host.ip_tags.length - 2} more
                      </button>
                    )}
                  </div>
                </td>
                <td>{host.ip_count}</td>
                {canEdit && (
                  <td>
                    <div className="table-actions">
                      <button
                        className="btn btn-secondary btn-small"
                        type="button"
                        onClick={() => onEdit(host)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn-danger btn-small"
                        type="button"
                        onClick={() => onDelete(host)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {popoverHost && (
        <TagPopover
          hostName={popoverHost.name}
          tags={popoverHost.ip_tags}
          onClose={() => setPopoverHost(null)}
          onSelect={(tag) => {
            onTag(tag);
            setPopoverHost(null);
          }}
        />
      )}
    </section>
  );
}
