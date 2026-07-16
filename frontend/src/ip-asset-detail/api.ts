import type { DetailResponse, EditValues } from "./types";

export class IPAssetApiError extends Error {
  constructor(
    public readonly messages: string[],
    public readonly status?: number,
  ) {
    super(messages[0] ?? "IP asset request failed.");
  }
}

async function readErrors(response: Response): Promise<string[]> {
  try {
    const payload = (await response.json()) as {
      detail?: string | string[] | Array<{ msg?: string }>;
    };
    if (typeof payload.detail === "string") return [payload.detail];
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) =>
          typeof item === "string"
            ? item
            : item.msg?.replace(/^Value error,\s*/, "") ?? "",
        )
        .filter(Boolean);
    }
  } catch {
    // Fall through to a stable error.
  }
  return [`IP asset request failed (${response.status}).`];
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    ...options,
  });
  if (
    response.redirected &&
    (response.url.includes("/ui/login") ||
      response.headers.get("location")?.includes("/ui/login"))
  ) {
    window.location.assign(`/ui/login?return_to=${window.location.pathname}`);
    throw new IPAssetApiError(["Authentication required."], 303);
  }
  if (!response.ok) {
    throw new IPAssetApiError(await readErrors(response), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function fetchIPAssetDetail(endpoint: string, signal?: AbortSignal) {
  return request<DetailResponse>(`${endpoint}/detail`, { signal });
}

export function updateIPAsset(endpoint: string, values: EditValues) {
  return request<void>(endpoint, {
    method: "PATCH",
    body: JSON.stringify({
      type: values.type,
      project_id: values.project_id ? Number(values.project_id) : null,
      host_id: values.host_id ? Number(values.host_id) : null,
      tags: values.tags,
      notes: values.notes,
    }),
  });
}

export function autoHostIPAsset(endpoint: string) {
  return request<{ host_id: number; host_name: string }>(`${endpoint}/auto-host`, {
    method: "POST",
  });
}

export function deleteIPAsset(
  endpoint: string,
  acknowledged: boolean,
  confirmIp: string,
) {
  return request<void>(endpoint, {
    method: "DELETE",
    body: JSON.stringify({
      acknowledged,
      confirm_ip: confirmIp,
    }),
  });
}
