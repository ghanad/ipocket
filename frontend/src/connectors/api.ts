import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type { ConnectorsConfig, ConnectorName, FieldValue, JobStart, ConnectorJob } from "./types";

export class ConnectorApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public loginUrl: string | null = null,
  ) { super(message); }
}

function connectorErrorMessage(error: SharedApiError): string {
  const detail = error.payload && typeof error.payload === "object"
    ? (error.payload as Record<string, unknown>).detail
    : undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(String).join(" ");
  return `Connector request failed (${error.status}).`;
}

async function request<T>(
  url: string,
  options: Parameters<typeof apiRequest>[1] = {},
): Promise<T> {
  let loginUrl: string | null = null;
  try {
    return await apiRequest<T>(url, {
      ...options,
      onAuthenticationRequired: (url) => {
        loginUrl = url;
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;
    if (error.status === 401 && loginUrl) {
      throw new ConnectorApiError("Authentication required.", 401, loginUrl);
    }
    throw new ConnectorApiError(connectorErrorMessage(error), error.status);
  }
}

export const fetchConnectorsConfig = (url: string, signal?: AbortSignal) => request<ConnectorsConfig>(url, { signal });
export const runConnector = (url: string, values: Record<string, FieldValue>) => request<JobStart>(url, { method: "POST", json: values });
export const fetchConnectorJob = (url: string, signal?: AbortSignal) => request<ConnectorJob>(url, { signal });

export function jobUrl(template: string, id: string): string {
  return template.replace("{job_id}", encodeURIComponent(id));
}

export function isConnectorName(value: string | null): value is ConnectorName {
  return ["vcenter", "prometheus", "elasticsearch", "cassandra", "ceph", "kubernetes"].includes(value ?? "");
}
