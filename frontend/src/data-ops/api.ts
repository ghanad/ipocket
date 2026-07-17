import type {
  DataOpsConfig,
  ImportKind,
  ImportMode,
  ImportResult,
  NmapResult,
} from "./types";

export class DataOpsApiError extends Error {}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg).replace(/^Value error,\s*/, "")
            : String(item),
        )
        .join(", ");
    }
  } catch {
    // Fall through to the status-based message.
  }
  return `Data operation failed (${response.status}).`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: { Accept: "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) throw new DataOpsApiError(await errorMessage(response));
  return response.json() as Promise<T>;
}

export function fetchDataOpsConfig(endpoint: string): Promise<DataOpsConfig> {
  return request<DataOpsConfig>(endpoint);
}

export function runDataImport(
  endpoint: string,
  kind: ImportKind,
  mode: ImportMode,
  formData: FormData,
): Promise<ImportResult | NmapResult> {
  const dryRun = mode === "dry-run" ? "1" : "0";
  return request(`${endpoint}/${kind}?dry_run=${dryRun}`, {
    method: "POST",
    body: formData,
  });
}
