import { useCallback, useEffect, useState } from "react";

import { fetchAboutData } from "./api";
import type { AboutData } from "./types";

interface AboutPageProps {
  endpoint: string;
}

function displayMetadata(value: string): string {
  return value.trim() || "unknown";
}

function PageHeader({ applicationName = "ipocket" }: { applicationName?: string }) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">About</p>
        <h1>About {applicationName}</h1>
        <p className="subtitle">
          Build details and direct operational endpoints for this installation.
        </p>
      </div>
    </header>
  );
}

export function AboutPage({ endpoint }: AboutPageProps) {
  const [data, setData] = useState<AboutData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAboutData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAboutData(endpoint));
    } catch {
      setError("About information could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    void loadAboutData();
  }, [loadAboutData]);

  if (loading) {
    return (
      <>
        <PageHeader />
        <section className="card" role="status" aria-live="polite">
          Loading About information…
        </section>
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageHeader />
        <section className="card">
          <h2>Unable to load About information</h2>
          <p className="subtitle" role="alert">
            {error}
          </p>
          <button
            className="btn btn-primary"
            type="button"
            onClick={() => void loadAboutData()}
          >
            Try again
          </button>
        </section>
      </>
    );
  }

  const metadata = [
    ["Version", data.build.version],
    ["Commit", data.build.commit],
    ["Build time", data.build.build_time],
  ];

  return (
    <>
      <PageHeader applicationName={displayMetadata(data.application.name)} />

      <section className="card" aria-labelledby="build-information-heading">
        <div className="card-header">
          <div>
            <h2 id="build-information-heading">Build information</h2>
            <p className="subtitle">Version details reported by this instance.</p>
          </div>
        </div>
        <dl className="detail-grid about-build-list">
          {metadata.map(([label, value]) => (
            <div className="detail-item" key={label}>
              <dt className="detail-label">{label}</dt>
              <dd className="detail-value about-metadata-value">
                {displayMetadata(value)}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card action-card" aria-labelledby="operational-links-heading">
        <h2 id="operational-links-heading">Operational links</h2>
        <p className="subtitle">Inspect service health or Prometheus metrics directly.</p>
        <div className="action-row">
          <a className="btn btn-secondary" href={data.links.health}>
            Health
          </a>
          <a className="btn btn-secondary" href={data.links.metrics}>
            Prometheus Metrics
          </a>
        </div>
      </section>
    </>
  );
}
