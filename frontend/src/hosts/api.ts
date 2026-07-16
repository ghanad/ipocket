import type { HostFormValues, HostsResponse } from "./types";

export class ApiError extends Error {
  constructor(public readonly messages: string[]) {
    super(messages[0] ?? "Host request failed.");
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
    // Use the stable fallback below.
  }
  return [`Host request failed (${response.status}).`];
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
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
    window.location.assign("/ui/login?return_to=/ui/hosts");
    throw new ApiError(["Authentication required."]);
  }
  if (!response.ok) throw new ApiError(await readErrors(response));
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function payload(values: HostFormValues) {
  const split = (value: string) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  const body: {
    name: string;
    notes: string;
    vendor_id: number | null;
    project_id?: number | null;
    os_ips: string[];
    bmc_ips: string[];
  } = {
    name: values.name,
    notes: values.notes,
    vendor_id: values.vendor_id ? Number(values.vendor_id) : null,
    os_ips: split(values.os_ips),
    bmc_ips: split(values.bmc_ips),
  };
  if (values.project_id !== "mixed") {
    body.project_id = values.project_id ? Number(values.project_id) : null;
  }
  return body;
}

export function fetchHosts(url: string, signal?: AbortSignal) {
  return request<HostsResponse>(url, { signal });
}

export function createHost(endpoint: string, values: HostFormValues) {
  return request<{ id: number; name: string }>(endpoint, {
    method: "POST",
    body: JSON.stringify(payload(values)),
  });
}

export function updateHost(
  endpoint: string,
  hostId: number,
  values: HostFormValues,
) {
  return request<{ id: number; name: string }>(`${endpoint}/${hostId}`, {
    method: "PATCH",
    body: JSON.stringify(payload(values)),
  });
}

export function deleteHost(
  endpoint: string,
  hostId: number,
  confirmName: string,
) {
  return request<void>(`${endpoint}/${hostId}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm_name: confirmName }),
  });
}
