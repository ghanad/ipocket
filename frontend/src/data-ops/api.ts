import { ApiError, apiRequest } from "../shared/apiClient";
import type {
  DataOpsConfig,
  ImportMode,
  ImportResult,
  NmapResult,
} from "./types";

export class DataOpsApiError extends Error {}

function dataOperationErrorMessage(error: ApiError): string {
  if (error.payload && typeof error.payload === "object") {
    const detail = (error.payload as Record<string, unknown>).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg).replace(/^Value error,\s*/, "")
            : String(item),
        )
        .join(", ");
    }
  }
  return `Data operation failed (${error.status}).`;
}

async function request<T>(
  url: string,
  options: Parameters<typeof apiRequest>[1] = {},
): Promise<T> {
  let authenticationRequired = false;
  try {
    return await apiRequest<T>(url, {
      ...options,
      onAuthenticationRequired: (loginUrl) => {
        authenticationRequired = true;
        window.location.assign(loginUrl);
      },
    });
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    throw new DataOpsApiError(
      authenticationRequired
        ? "Authentication required."
        : dataOperationErrorMessage(error),
    );
  }
}

function withDryRun(endpoint: string, dryRun: "0" | "1"): string {
  const fragmentIndex = endpoint.indexOf("#");
  const base = fragmentIndex === -1 ? endpoint : endpoint.slice(0, fragmentIndex);
  const fragment = fragmentIndex === -1 ? "" : endpoint.slice(fragmentIndex);
  let separator = "?";
  if (base.includes("?")) {
    separator = base.endsWith("?") || base.endsWith("&") ? "" : "&";
  }
  return `${base}${separator}dry_run=${dryRun}${fragment}`;
}

export function fetchDataOpsConfig(endpoint: string): Promise<DataOpsConfig> {
  return request<DataOpsConfig>(endpoint);
}

export function runDataImport(
  endpoint: string,
  mode: ImportMode,
  formData: FormData,
): Promise<ImportResult | NmapResult> {
  const dryRun = mode === "dry-run" ? "1" : "0";
  return request(withDryRun(endpoint, dryRun), {
    method: "POST",
    body: formData,
  });
}
