import { ApiError as SharedApiError, apiRequest } from "../shared/apiClient";
import type { HostFormValues, HostsResponse } from "./types";

export class ApiError extends Error {
  constructor(public readonly messages: string[]) {
    super(messages[0] ?? "Host request failed.");
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
      messages = typeof detail === "string" || Array.isArray(detail)
        ? error.messages
        : [`Host request failed (${error.status}).`];
    } else {
      messages = [`Host request failed (${error.status}).`];
    }
    throw new ApiError(messages);
  }
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
    json: payload(values),
  });
}

export function updateHost(
  endpoint: string,
  hostId: number,
  values: HostFormValues,
) {
  return request<{ id: number; name: string }>(`${endpoint}/${hostId}`, {
    method: "PATCH",
    json: payload(values),
  });
}

export function deleteHost(
  endpoint: string,
  hostId: number,
  confirmName: string,
) {
  return request<void>(`${endpoint}/${hostId}`, {
    method: "DELETE",
    json: { confirm_name: confirmName },
  });
}
