import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";

export interface BMCTargetAsset {
  id: number;
  ip_address: string;
}

export interface BMCTarget {
  host_id: number;
  host_name: string;
  vendor_name: string | null;
  bmc_assets: BMCTargetAsset[];
}

export interface BMCScanResult {
  host_id: number;
  host_name: string;
  bmc_ip: string | null;
  detected_vendor: string | null;
  confidence: "high" | "medium" | "low" | null;
  fingerprint_summary: string | null;
  status: "matched" | "unmatched" | "timeout" | "error";
  error: string | null;
}

export interface BMCScanResponse {
  results: BMCScanResult[];
  total: number;
  matched_count: number;
}

export interface BMCApplyResult {
  applied: { host_id: number; host_name: string; vendor_name: string }[];
  count: number;
}

export class BMCDiscoveryApiError extends Error {
  constructor(public readonly messages: string[]) {
    super(messages[0] ?? "BMC Discovery request failed.");
  }
}

async function request<T>(
  url: string,
  options: Parameters<typeof apiRequest>[1] = {},
): Promise<T> {
  let authenticationRequired = false;
  try {
    return await apiRequest<T>(url, {
      ...options,
      onAuthenticationRequired: () => {
        authenticationRequired = true;
        window.location.assign("/ui/login?return_to=/ui/hosts");
      },
    });
  } catch (error) {
    if (!(error instanceof SharedApiError)) throw error;

    let messages: string[];
    if (authenticationRequired) {
      messages = ["Authentication required."];
    } else if (error.payload && typeof error.payload === "object") {
      const detail = (error.payload as Record<string, unknown>).detail;
      messages =
        typeof detail === "string" || Array.isArray(detail)
          ? error.messages
          : [`Discovery request failed (${error.status}).`];
    } else {
      messages = [`Discovery request failed (${error.status}).`];
    }
    throw new BMCDiscoveryApiError(messages);
  }
}

export async function fetchBMCTargets(
  hostIds?: number[],
): Promise<{ targets: BMCTarget[]; total: number }> {
  const params = new URLSearchParams();
  if (hostIds && hostIds.length > 0) {
    hostIds.forEach((id) => params.append("host_id", String(id)));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<{ targets: BMCTarget[]; total: number }>(
    `/api/hosts/bmc-discovery/targets${query}`,
  );
}

export async function scanBMCVendors(payload?: {
  host_ids?: number[];
  timeout?: number;
  concurrency?: number;
}): Promise<BMCScanResponse> {
  return request<BMCScanResponse>("/api/hosts/bmc-discovery/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}

export async function applyBMCVendors(
  items: { host_id: number; vendor_name: string }[],
): Promise<BMCApplyResult> {
  return request<BMCApplyResult>("/api/hosts/bmc-discovery/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
}
