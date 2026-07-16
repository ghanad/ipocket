import { useCallback, useEffect, useState } from "react";

import { AssetTable } from "./AssetTable";
import { fetchHostDetail, HostDetailApiError } from "./api";
import type { HostDetailAsset, HostDetailResponse } from "./types";

function AssetSection({
  id,
  title,
  description,
  assets,
  emptyText,
  includeType = false,
}: {
  id: string;
  title: string;
  description: string;
  assets: HostDetailAsset[];
  emptyText: string;
  includeType?: boolean;
}) {
  return (
    <section className="card">
      <div className="card-header">
        <div>
          <h2 id={id}>{title}</h2>
          <p className="subtitle">{description}</p>
        </div>
        <span className="tag">{assets.length}</span>
      </div>
      {assets.length ? (
        <AssetTable assets={assets} headingId={id} includeType={includeType} />
      ) : (
        <p className="empty-state">{emptyText}</p>
      )}
    </section>
  );
}

export function HostDetailPage({ endpoint }: { endpoint: string }) {
  const [data, setData] = useState<HostDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<HostDetailApiError | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchHostDetail(endpoint, signal));
    } catch (loadError) {
      if (!(loadError instanceof DOMException)) {
        setError(
          loadError instanceof HostDetailApiError
            ? loadError
            : new HostDetailApiError("Host details could not be loaded."),
        );
      }
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (loading) {
    return (
      <section className="card empty-state" role="status">
        Loading host details…
      </section>
    );
  }
  if (error?.status === 404) {
    return (
      <section className="card empty-state" role="alert">
        <h1>Host not found</h1>
        <p>The requested Host does not exist.</p>
        <a className="btn btn-secondary" href="/ui/hosts">
          Back to hosts
        </a>
      </section>
    );
  }
  if (error || !data) {
    return (
      <section className="card empty-state" role="alert">
        <p>Host details could not be loaded. Please try again.</p>
        <button className="btn btn-secondary" type="button" onClick={() => void load()}>
          Try again
        </button>
      </section>
    );
  }

  const linkedStatus =
    data.summary.linked_count === 0
      ? "No linked IPs"
      : `${data.summary.linked_count} linked IP${
          data.summary.linked_count === 1 ? "" : "s"
        }`;

  return (
    <>
      <section className="page-header ip-detail-header">
        <div>
          <p className="eyebrow">Host</p>
          <h1>{data.host.name}</h1>
          <div className="ip-detail-meta">
            <span className="tag">Vendor: {data.host.vendor}</span>
            <span
              className={`tag${data.summary.linked_count === 0 ? " tag-warning" : ""}`}
            >
              Status: {linkedStatus}
            </span>
            <span className="tag">OS: {data.summary.os_count}</span>
            <span className="tag">BMC: {data.summary.bmc_count}</span>
          </div>
        </div>
        <div className="header-actions">
          <a className="btn btn-secondary" href="/ui/hosts">
            Back to hosts
          </a>
        </div>
      </section>

      <section className="card">
        <h2>Details</h2>
        <div className="detail-grid">
          <div className="detail-item">
            <p className="detail-label">Host name</p>
            <p className="detail-value">{data.host.name}</p>
          </div>
          <div className="detail-item">
            <p className="detail-label">Vendor</p>
            <p className="detail-value">{data.host.vendor}</p>
          </div>
          <div className="detail-item">
            <p className="detail-label">Linked IPs</p>
            <p className="detail-value">{data.summary.linked_count}</p>
          </div>
          <div className="detail-item">
            <p className="detail-label">OS / BMC</p>
            <p className="detail-value">
              {data.summary.os_count} / {data.summary.bmc_count}
            </p>
          </div>
          <div className="detail-item detail-item-wide">
            <p className="detail-label">Notes</p>
            <p className="detail-value">{data.host.notes}</p>
          </div>
        </div>
      </section>

      <AssetSection
        id="host-os-ips-heading"
        title="OS IPs"
        description="Operating-system addresses linked to this host."
        assets={data.groups.os}
        emptyText="No OS IPs linked."
      />
      <AssetSection
        id="host-bmc-ips-heading"
        title="BMC IPs"
        description="Out-of-band management addresses linked to this host."
        assets={data.groups.bmc}
        emptyText="No BMC IPs linked."
      />
      {data.groups.other.length > 0 && (
        <AssetSection
          id="host-other-ips-heading"
          title="Other linked IPs"
          description="VM, VIP, and other records currently attached to this host."
          assets={data.groups.other}
          emptyText=""
          includeType
        />
      )}
    </>
  );
}
