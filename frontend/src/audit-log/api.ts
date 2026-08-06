import { apiRequest } from "../shared/apiClient";
import type { AuditLogResponse } from "./types";

export async function fetchAuditLogs(
  endpoint: string,
  query = "",
  signal?: AbortSignal,
): Promise<AuditLogResponse> {
  const url = `${endpoint}${query ? `?${query}` : ""}`;
  return apiRequest<AuditLogResponse>(url, { signal });
}
