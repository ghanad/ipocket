import type { CSSProperties } from "react";

import { tagColorStyle } from "../shared/tagColor";
import type { HostDetailAsset } from "./types";

export function AssetTable({
  assets,
  headingId,
  includeType = false,
}: {
  assets: HostDetailAsset[];
  headingId: string;
  includeType?: boolean;
}) {
  return (
    <div className="table-wrapper">
      <table className="table" aria-labelledby={headingId}>
        <thead>
          <tr>
            <th>IP address</th>
            {includeType && <th>Type</th>}
            <th>Project</th>
            <th>Tags</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.id}>
              <td>
                <a className="mono" href={`/ui/ip-assets/${asset.id}`}>
                  {asset.ip_address}
                </a>
              </td>
              {includeType && (
                <td>
                  <span className="tag">{asset.type}</span>
                </td>
              )}
              <td>
                {asset.project ? (
                  <span
                    className="tag tag-project"
                    style={
                      {
                        "--project-color": asset.project.color || "#94a3b8",
                      } as CSSProperties
                    }
                  >
                    {asset.project.name}
                  </span>
                ) : (
                  <span className="tag tag-warning">Unassigned</span>
                )}
              </td>
              <td>
                <div className="ip-detail-tags">
                  {asset.tags.length ? (
                    asset.tags.map((tag) => (
                      <span
                        className="tag tag-color"
                        key={tag.name}
                        style={tagColorStyle(tag.color)}
                      >
                        {tag.name}
                      </span>
                    ))
                  ) : (
                    <span className="tag">No tags</span>
                  )}
                </div>
              </td>
              <td>{asset.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
