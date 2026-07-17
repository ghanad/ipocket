import type { ConnectorsConfig, ConnectorName, FieldValue, JobStart, ConnectorJob } from "./types";

export class ConnectorApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public loginUrl: string | null = null,
  ) { super(message); }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) return payload.detail.map(String).join(" ");
  } catch { /* use safe fallback */ }
  return `Connector request failed (${response.status}).`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (
    response.redirected &&
    (response.url.includes("/ui/login") ||
      response.headers.get("location")?.includes("/ui/login"))
  ) {
    throw new ConnectorApiError(
      "Authentication required.",
      401,
      `/ui/login?return_to=${encodeURIComponent(
        `${window.location.pathname}${window.location.search}`,
      )}`,
    );
  }
  if (!response.ok) throw new ConnectorApiError(await errorMessage(response), response.status);
  return response.json() as Promise<T>;
}

export const fetchConnectorsConfig = (url: string, signal?: AbortSignal) => request<ConnectorsConfig>(url, { signal });
export const runConnector = (url: string, values: Record<string, FieldValue>) => request<JobStart>(url, { method: "POST", body: JSON.stringify(values) });
export const fetchConnectorJob = (url: string, signal?: AbortSignal) => request<ConnectorJob>(url, { signal });

export function jobUrl(template: string, id: string): string {
  return template.replace("{job_id}", encodeURIComponent(id));
}

export function isConnectorName(value: string | null): value is ConnectorName {
  return ["vcenter", "prometheus", "elasticsearch", "cassandra", "ceph", "kubernetes"].includes(value ?? "");
}
